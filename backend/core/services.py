"""All state transitions serialize on the owner row, including GET settlement."""

import hashlib
import json
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError

from . import engine
from .models import Action, Daily, Habit, HabitLog, Inventory, Pet, Profile, RewardLedger, Session
from .serializers import HabitSerializer


class Conflict(APIException):
    status_code = 409
    default_code = "conflict"


def lock_owner(user):
    get_user_model().objects.select_for_update().get(pk=user.pk)


def context(user, now=None):
    now = now or timezone.now()
    profile, _ = Profile.objects.get_or_create(user=user)
    pet = Pet.objects.filter(user=user).order_by("-generation").first()
    if pet is None:
        pet = Pet.objects.create(user=user, born_at=now, updated_at=now)
    inventory, _ = Inventory.objects.get_or_create(user=user)
    day = now.astimezone(ZoneInfo(profile.timezone)).date()
    daily, _ = Daily.objects.get_or_create(user=user, date=day)
    engine.advance(pet, now)
    if pet.state == "dead" and pet.died_at is None:
        pet.died_at = pet.critical_since + timedelta(hours=48)
    pet.save()
    return profile, pet, inventory, daily


def pet_json(pet, daily, completed):
    data = model_to_dict(pet, exclude=["user"])
    data["mood"] = engine.mood(
        pet,
        daily.step_reward,
        completed,
        daily.fed,
        min(daily.play_count, 3) * 3 + (6 if daily.walked else 0),
    )
    data["evolution"] = engine.evolution(pet.level, pet.study_score, pet.activity_score)
    data["age_days"] = max(0, ((pet.died_at or timezone.now()) - pet.born_at).days)
    return data


def snapshot(user, ctx=None):
    profile, pet, inventory, daily = ctx or context(user)
    logs = {log.habit_id: log for log in HabitLog.objects.filter(habit__user=user, date=daily.date)}
    habits = []
    for habit in Habit.objects.filter(user=user, active=True).order_by("id"):
        h = HabitSerializer(habit).data
        log = logs.get(habit.pk)
        h.update(progress=log.progress if log else 0, completed=log.completed if log else False)
        habits.append(h)
    return {
        "server_time": timezone.now(),
        "date": daily.date,
        "timezone": profile.timezone,
        "pet": pet_json(pet, daily, sum(log.completed for log in logs.values())),
        "inventory": {"food": inventory.food, "coin": inventory.coin},
        "habits": habits,
        "health": {
            "steps": daily.steps,
            "sleep_minutes": daily.sleep_minutes,
            "step_reward": daily.step_reward,
            "observed_at": daily.health_observed_at,
            "steps_observed_at": daily.steps_observed_at,
        },
        "water_count": daily.water_count,
        "sessions": [
            {
                "id": s.id,
                "kind": s.kind,
                "habit_id": s.habit_id,
                "started_at": s.started_at,
                "start_steps": s.start_steps,
            }
            for s in Session.objects.filter(user=user, ended_at__isnull=True)
        ],
        "message": {
            "emotion": "hungry" if pet.hunger < 40 else "happy",
            "message": "完成一个小目标，一起照顾今天的自己。",
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
        log.completed = log.reward_claimed = True
        RewardLedger.objects.create(
            user=user,
            source=f"habit:{habit.id}:{daily.date}",
            resource=habit.reward_type,
            amount=habit.reward_amount,
        )
        if habit.reward_type == "xp":
            engine.gain_xp(pet, habit.reward_amount)
        else:
            setattr(
                inventory,
                habit.reward_type,
                getattr(inventory, habit.reward_type) + habit.reward_amount,
            )
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
    profile, pet, inventory, daily = context(user, now)
    if data["generation"] != pet.generation:
        raise Conflict("Pet generation changed; refresh and review this action")
    kind, payload = data["kind"], data["payload"]
    if pet.state == "dead" and kind != "rebirth":
        raise Conflict("Pet has died; rebirth is required")
    if kind == "feed":
        if inventory.food < 1:
            raise Conflict("No food available")
        try:
            engine.feed(pet)
        except ValueError as exc:
            raise Conflict(str(exc))
        inventory.food -= 1
        daily.fed = True
        RewardLedger.objects.create(
            user=user, source=f"action:{data['id']}", resource="food", amount=-1
        )
    elif kind == "water":
        daily.water_count += 1
        if daily.water_count <= 6:
            pet.hydration = engine.clamp(pet.hydration + 15)
    elif kind == "play":
        daily.play_count += 1
        if daily.play_count <= 3:
            pet.bond = engine.clamp(pet.bond + 1)
            engine.gain_xp(pet, 2)
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
        Session.objects.filter(user=user, ended_at__isnull=True).update(ended_at=now)
        pet = Pet.objects.create(
            user=user, name=pet.name, generation=pet.generation + 1, born_at=now, updated_at=now
        )
    elif kind in ("focus_start", "walk_start"):
        session_kind = kind.split("_")[0]
        if Session.objects.filter(user=user, kind=session_kind, ended_at__isnull=True).exists():
            raise Conflict("A session is already active")
        habit = owned_habit(user, payload) if session_kind == "focus" else None
        if session_kind == "walk" and (
            daily.steps_observed_at is None or now - daily.steps_observed_at > timedelta(minutes=5)
        ):
            raise Conflict("Sync current steps before starting a walk")
        if session_kind == "walk" and daily.walked:
            raise Conflict("Walk reward already earned today")
        Session.objects.create(user=user, kind=session_kind, habit=habit, start_steps=daily.steps)
    elif kind in ("focus_finish", "walk_finish"):
        session_kind = kind.split("_")[0]
        session = Session.objects.filter(
            user=user, kind=session_kind, ended_at__isnull=True
        ).first()
        if not session:
            raise Conflict("No active session")
        if session.started_at.astimezone(ZoneInfo(profile.timezone)).date() != daily.date:
            raise Conflict("Session belongs to a previous day; cancel it and start again")
        if session_kind == "walk":
            if daily.walked or daily.steps - session.start_steps < 1000:
                raise Conflict("Walk at least 1000 steps; only one reward per day")
            daily.walked = True
            pet.bond = engine.clamp(pet.bond + 5)
            engine.gain_xp(pet, 10)
            pet.activity_score += 1
        else:
            if not session.habit or not session.habit.active:
                raise Conflict("Habit is no longer available")
            elapsed = int((now - session.started_at).total_seconds() // 60)
            if elapsed < session.habit.target:
                raise Conflict("Focus target has not elapsed yet")
            complete_progress(user, pet, inventory, daily, session.habit)
        session.ended_at = now
        session.save()
    pet.save()
    inventory.save()
    daily.save()
    result = snapshot(user, (profile, pet, inventory, daily))
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
    profile, pet, inventory, daily = context(user, now)
    observed = data.get("observed_at", now)
    if (
        observed > now + timedelta(minutes=5)
        or observed.astimezone(ZoneInfo(profile.timezone)).date() != daily.date
    ):
        raise ValidationError("Health observation must belong to today, not the future")
    if daily.health_observed_at and observed < daily.health_observed_at:
        return snapshot(user, (profile, pet, inventory, daily))
    if data.get("steps") is not None:
        daily.steps = data["steps"]
        daily.steps_observed_at = observed
    daily.health_observed_at = observed
    daily.step_reward = max(
        daily.step_reward,
        15
        if daily.steps >= 8000
        else 10
        if daily.steps >= 5000
        else 5
        if daily.steps >= 2000
        else 0,
    )
    if data.get("sleep_minutes") is not None:
        daily.sleep_minutes = data["sleep_minutes"]
        if pet.state != "dead":
            pet.energy = engine.clamp(100 * daily.sleep_minutes / profile.sleep_target)
    daily.save()
    pet.save()
    return snapshot(user, (profile, pet, inventory, daily))
