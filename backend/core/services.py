"""All state transitions serialize on the owner row, including GET settlement."""

import hashlib
import json
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError

from . import engine, fitness
from .catalog import ITEMS
from .models import (
    Action,
    Daily,
    Habit,
    HabitLog,
    Inventory,
    InventoryItem,
    Pet,
    Profile,
    RewardChoice,
    RewardLedger,
    Session,
)
from .serializers import HabitSerializer


class Conflict(APIException):
    status_code = 409
    default_code = "conflict"


def lock_owner(user):
    get_user_model().objects.select_for_update().get(pk=user.pk)


def context(user, now=None, settle=True):
    now = now or timezone.now()
    profile, _ = Profile.objects.get_or_create(user=user)
    pet = Pet.objects.filter(user=user).order_by("-generation").first()
    if pet is None:
        pet = Pet.objects.create(user=user, born_at=now, updated_at=now, last_decay_at=now)
    inventory, _ = Inventory.objects.get_or_create(user=user)
    day = now.astimezone(ZoneInfo(profile.timezone)).date()
    daily, _ = Daily.objects.get_or_create(user=user, date=day)
    fitness.initialize(pet, profile, now)
    if settle:
        fitness.settle(pet, now)
    return profile, pet, inventory, daily


def pet_json(pet):
    data = model_to_dict(pet, exclude=["user"])
    data["visual_state"] = engine.visual_state(pet)
    data["fitness_status"] = fitness.status(pet.fitness)
    data["evolution"] = engine.evolution(pet.level, pet.study_score, pet.activity_score)
    data["age_days"] = max(0, ((pet.died_at or timezone.now()) - pet.born_at).days)
    return data


def snapshot(user, ctx=None):
    profile, pet, inventory, daily = ctx or context(user)
    logs = {log.habit_id: log for log in HabitLog.objects.filter(habit__user=user, date=daily.date)}
    if pet.state != "dead" and pet.hunger >= 70 and pet.mood >= 70 and not daily.care_bonus_claimed:
        # All snapshot callers hold the owner lock. The daily flag also survives rebirth.
        engine.gain_xp(pet, 5)
        daily.care_bonus_claimed = True
        pet.save(update_fields=["xp", "level"])
        daily.save(update_fields=["care_bonus_claimed"])
        RewardLedger.objects.create(user=user, source=f"care:{daily.date}", resource="xp", amount=5)
    habits = []
    for habit in Habit.objects.filter(user=user, active=True).order_by("id"):
        h = HabitSerializer(habit).data
        log = logs.get(habit.pk)
        h.update(progress=log.progress if log else 0, completed=log.completed if log else False)
        habits.append(h)
    stock = [{**ITEMS[row.item_id], "quantity": row.quantity}
             for row in InventoryItem.objects.filter(user=user, quantity__gt=0)]
    return {
        "server_time": timezone.now(),
        "date": daily.date,
        "timezone": profile.timezone,
        "pet": pet_json(pet),
        "inventory": {"food": sum(row["quantity"] for row in stock if row["category"] == "food"),
                      "coin": inventory.coin, "items": stock},
        "personality": profile.personality,
        "pending_rewards": [{"id": r.id, "habit_id": r.completion.habit_id, "name": r.completion.habit.name, "date": r.completion.date} for r in RewardChoice.objects.filter(completion__habit__user=user, claimed_at__isnull=True).select_related("completion__habit").order_by("id")],
        "habits": habits,
        "health": fitness.summary(pet, timezone.now()),
        "water_count": daily.water_count,
        "care_bonus_claimed": daily.care_bonus_claimed,
        "sessions": [
            {
                "id": s.id,
                "kind": s.kind,
                "habit_id": s.habit_id,
                "started_at": s.started_at,
                "start_steps": s.start_steps,
            }
            for s in Session.objects.filter(user=user, kind="focus", ended_at__isnull=True)
        ],
        "message": {
            "emotion": engine.visual_state(pet),
            "message": "One small goal. A little care for both of us.",
            "suggested_action": "habits",
            "urgency": "low",
            "source": "rule",
        },
    }


@transaction.atomic
def today(user):
    lock_owner(user)
    return snapshot(user)


def positive(payload, key):
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000:
        raise ValidationError({key: "Expected an integer between 1 and 10000"})
    return value


def owned_habit(user, payload):
    hid = positive(payload, "habit_id")
    try:
        return Habit.objects.get(pk=hid, user=user, active=True)
    except Habit.DoesNotExist:
        raise NotFound("Habit not found")


def complete_progress(user, pet, inventory, daily, habit, amount=None):
    log, _ = HabitLog.objects.get_or_create(habit=habit, date=daily.date)
    if log.completed:
        return
    log.progress = min(habit.target, log.progress + amount) if amount is not None else habit.target
    if log.progress >= habit.target:
        log.completed = True
        log.save()
        RewardChoice.objects.get_or_create(completion=log)
        pet.bond = engine.clamp(pet.bond + 1)
        pet.completed_habits += 1
        if habit.category in ("study", "reading", "work"):
            pet.study_score += 1
        if habit.category == "exercise":
            pet.activity_score += 1
    log.save()


@transaction.atomic
def apply_action(user, data):
    lock_owner(user)
    now = timezone.now()
    occurred = data.get("occurred_at", now)
    if occurred > now + timedelta(minutes=5) or occurred < now - timedelta(days=7):
        raise ValidationError("Action timestamp must be within the last 7 days")
    canonical = {k: v for k, v in data.items() if k != "id"}
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, default=str).encode()
    ).hexdigest()
    existing = Action.objects.filter(user=user, operation_id=data["id"]).first()
    if existing:
        if existing.fingerprint != fingerprint:
            raise Conflict("Operation ID was already used with different content")
        return existing.result
    current_pet = Pet.objects.filter(user=user).order_by("-generation").first()
    # Replay saved care in order before the client's final today/health sync.
    # Never rewind a timeline already committed by another device or worker.
    action_time = max(min(occurred, now), current_pet.updated_at if current_pet else now)
    profile, pet, inventory, daily = context(user, action_time)
    if data["generation"] != pet.generation:
        raise Conflict("Pet generation changed; refresh and review this action")
    kind, payload = data["kind"], data["payload"]
    if pet.state == "dead" and kind != "rebirth":
        raise Conflict("Pet has died; rebirth is required")
    if kind in ("feed", "use_item", "water"):
        pet.rest_at = None
    if kind == "feed":
        raise Conflict("Choose a specific Food item from your inventory")
    elif kind == "claim_reward":
        reward = RewardChoice.objects.filter(pk=positive(payload, "reward_id"), completion__habit__user=user).select_related("completion").first()
        if reward is None:
            raise NotFound("Reward not found")
        if reward.claimed_at:
            raise Conflict("This reward was already claimed")
        category = payload.get("category")
        if type(category) is not int or category not in (0, 1):
            raise ValidationError("Choose Food (0) or Toy (1)")
        choices = [item for item in ITEMS.values() if item["category"] == ("food" if category == 0 else "toy")]
        selected = secrets.choice(choices)
        row, _ = InventoryItem.objects.get_or_create(user=user, item_id=selected["id"])
        row.quantity += 1
        row.save()
        reward.item_id = selected["id"]
        reward.claimed_at = now
        reward.save()
        reward.completion.reward_claimed = True
        reward.completion.save(update_fields=["reward_claimed"])
        RewardLedger.objects.create(user=user, source=f"reward:{reward.id}", resource=selected["category"], amount=1)
    elif kind == "use_item":
        item_id = positive(payload, "item_id")
        row = InventoryItem.objects.filter(user=user, item_id=item_id, quantity__gt=0).first()
        item = ITEMS.get(item_id)
        if row is None or item is None:
            raise Conflict("This item is no longer available")
        if item["category"] == "food":
            try:
                engine.feed(pet, item["effect"])
            except ValueError as exc:
                raise Conflict(str(exc))
            daily.fed = True
        else:
            if pet.mood >= 100:
                raise Conflict("Mood is already full")
            pet.mood = engine.clamp(pet.mood + item["effect"])
        row.quantity -= 1
        row.save()
        RewardLedger.objects.create(user=user, source=f"action:{data['id']}", resource=item["category"], amount=-1)
    elif kind == "water":
        daily.water_count += 1
        pet.hydration = engine.clamp(pet.hydration + 20)
        pet.water_zero_since = None
    elif kind == "rest":
        if pet.rest_at is None:
            pet.rest_at = action_time
    elif kind == "wake":
        pet.rest_at = None
    elif kind in ("complete", "progress"):
        habit = owned_habit(user, payload)
        complete_progress(
            user,
            pet,
            inventory,
            daily,
            habit,
            positive(payload, "amount") if kind == "progress" else None,
        )
    elif kind == "rebirth":
        if pet.state != "dead":
            raise Conflict("Only a dead pet can be reborn")
        Session.objects.filter(user=user, kind="focus", ended_at__isnull=True).update(ended_at=now)
        pet = Pet.objects.create(
            user=user, name=pet.name, species=pet.species, gender=pet.gender,
            generation=pet.generation + 1, born_at=now, updated_at=now, last_decay_at=now
        )
    elif kind == "focus_start":
        if Session.objects.filter(user=user, kind="focus", ended_at__isnull=True).exists():
            raise Conflict("A focus session is already active")
        habit = owned_habit(user, payload)
        Session.objects.create(user=user, kind="focus", habit=habit)
    elif kind == "focus_finish":
        session = Session.objects.filter(user=user, kind="focus", ended_at__isnull=True).first()
        if not session:
            raise Conflict("No active focus session")
        if session.started_at.astimezone(ZoneInfo(profile.timezone)).date() != daily.date:
            raise Conflict("Session belongs to a previous day; cancel it and start again")
        if not session.habit or not session.habit.active:
            raise Conflict("Habit is no longer available")
        elapsed = int((now - session.started_at).total_seconds() // 60)
        if elapsed < session.habit.target:
            raise Conflict("Focus target has not elapsed yet")
        complete_progress(user, pet, inventory, daily, session.habit)
        session.ended_at = now
        session.save()
    fitness.initialize(pet, profile, now)
    pet.save()
    inventory.save()
    daily.save()
    result = snapshot(user, (profile, pet, inventory, daily))
    if kind == "use_item":
        result["used_item_id"] = payload["item_id"]
    # Persist exactly the JSON wire form for stable retries.
    from rest_framework.renderers import JSONRenderer

    result = json.loads(JSONRenderer().render(result))
    Action.objects.create(
        user=user,
        operation_id=data["id"],
        fingerprint=fingerprint,
        kind=kind,
        generation=data["generation"],
        occurred_at=occurred,
        result=result,
    )
    return result


@transaction.atomic
def sync_health(user, data):
    lock_owner(user)
    now = timezone.now()
    profile, pet, inventory, daily = context(user, now, settle=False)
    if data.get("generation", pet.generation) != pet.generation:
        raise Conflict("Pet generation changed; refresh before syncing health")
    observed = data.get("observed_at", now)
    if observed > now + timedelta(minutes=5):
        raise ValidationError("Health observation cannot be in the future")
    if "days" in data:
        days = data["days"]
    else:
        if observed.astimezone(ZoneInfo(pet.fitness_timezone)).date() != now.astimezone(ZoneInfo(pet.fitness_timezone)).date():
            raise ValidationError("Legacy health observations must belong to today")
        days = [{"date": now.astimezone(ZoneInfo(pet.fitness_timezone)).date(), **{k: data[k] for k in ("steps", "sleep_minutes") if k in data}}]
    fitness.record(pet, days, observed, now)
    fitness.settle(pet, now)
    return snapshot(user, (profile, pet, inventory, daily))


@transaction.atomic
def update_pet_details(user, data):
    lock_owner(user)
    profile, pet, inventory, daily = context(user)
    if data["generation"] != pet.generation:
        raise Conflict("Your pet's generation changed. Refresh before editing.")
    if pet.state == "dead":
        raise Conflict("Start a new generation before editing your pet.")
    for field in ("name", "species"):
        if field in data:
            setattr(pet, field, data[field])
    if "personality" in data:
        profile.personality = data["personality"]
        profile.save(update_fields=["personality"])
    pet.details_configured = True
    pet.save()
    return snapshot(user, (profile, pet, inventory, daily))
