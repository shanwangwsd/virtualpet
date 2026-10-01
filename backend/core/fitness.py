"""Calendar-day Fitness, settled only from complete HealthKit observations.

Callers hold services.lock_owner inside a transaction. Observation timestamps
prevent a partial morning/night reading from being finalized by a later GET.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from . import engine
from .models import FitnessDay


def step_delta(steps):
    if steps is None:
        return 0
    return 30 if steps >= 5000 else 10 if steps >= 1000 else 0 if steps >= 500 else -10


def sleep_delta(minutes):
    if minutes is None:
        return 0
    return 10 if minutes >= 480 else 0 if minutes >= 300 else -10


def status(value):
    return "energetic" if value >= 70 else "normal" if value >= 40 else "tired" if value >= 20 else "weak"


def initialize(pet, profile, now):
    if pet.fitness_started_on is None:
        pet.fitness_timezone = profile.timezone
        pet.fitness_started_on = now.astimezone(ZoneInfo(profile.timezone)).date()


def window_end(pet, day, kind):
    zone = ZoneInfo(pet.fitness_timezone)
    if kind == "step":
        return datetime.combine(day + timedelta(days=1), time(), zone)
    return datetime.combine(day, time(12), zone)


def record(pet, days, observed, now):
    today = now.astimezone(ZoneInfo(pet.fitness_timezone)).date()
    for item in days:
        day = item["date"]
        if not pet.fitness_started_on <= day <= today:
            raise ValidationError("Health dates must be between Fitness activation and today")
        row, _ = FitnessDay.objects.get_or_create(pet=pet, date=day)
        for value_key, timestamp, result in [("steps", "steps_observed_at", "step_delta"), ("sleep_minutes", "sleep_observed_at", "sleep_delta")]:
            previous = getattr(row, timestamp)
            if value_key in item and getattr(row, result) is None and (previous is None or observed >= previous):
                setattr(row, value_key, item[value_key])
                setattr(row, timestamp, observed)
        row.save()


def settle(pet, now):
    rows = FitnessDay.objects.filter(pet=pet).filter(Q(step_delta__isnull=True) | Q(sleep_delta__isnull=True)).order_by("date")
    events = []
    for row in rows:
        for kind, seen, delta in [("step", row.steps_observed_at, row.step_delta), ("sleep", row.sleep_observed_at, row.sleep_delta)]:
            end = window_end(pet, row.date, kind)
            if seen is not None and seen >= end and end <= now and delta is None:
                events.append((end, kind, row))
    for end, kind, row in sorted(events, key=lambda event: event[0]):
        if pet.state == "dead":
            break
        cursor_key = f"last_{kind}_settlement_date"
        cursor = getattr(pet, cursor_key)
        expected = cursor + timedelta(days=1) if cursor else pet.fitness_started_on
        if row.date != expected:
            continue  # Do not lose missing dates by jumping the cursor forward.
        engine.advance(pet, max(end, pet.updated_at))
        if pet.state == "dead":
            break
        if kind == "sleep" and row.sleep_minutes is not None:
            pet.energy = engine.clamp(pet.energy + min(40, (row.sleep_minutes // 60) * 5))
            pet.sleep_deprived_until = end + timedelta(hours=24) if row.sleep_minutes < 300 else None
        delta = step_delta(row.steps) if kind == "step" else sleep_delta(row.sleep_minutes)
        pet.fitness = engine.clamp(pet.fitness + delta)
        setattr(row, f"{kind}_delta", delta)
        row.save(update_fields=[f"{kind}_delta"])
        setattr(pet, cursor_key, row.date)
        if pet.fitness <= 0:
            pet.state = "dead"
            pet.died_at = pet.updated_at
            pet.rest_at = None
            break
    engine.advance(pet, now)
    pet.save()


def summary(pet, now):
    day = now.astimezone(ZoneInfo(pet.fitness_timezone)).date()
    current = FitnessDay.objects.filter(pet=pet, date=day).first()
    latest_sleep = FitnessDay.objects.filter(pet=pet, sleep_minutes__isnull=False).order_by("-date").first()
    steps = current.steps if current else None
    sleep = current.sleep_minutes if current else None
    return {
        "steps": steps or 0,
        "steps_observed_at": current.steps_observed_at if current and steps is not None else None,
        "sleep_minutes": latest_sleep.sleep_minutes if latest_sleep else None,
        "sleep_date": latest_sleep.date if latest_sleep else None,
        "sleep_preview_minutes": sleep,
        "step_delta_preview": step_delta(steps) if steps is not None else None,
        "sleep_delta_preview": sleep_delta(sleep) if sleep is not None else None,
        "sleep_settled_today": bool(current and current.sleep_delta is not None),
        "step_reward": 0,  # Compatibility field; the old live mood reward is retired.
        "fitness_timezone": pet.fitness_timezone,
        "fitness_started_on": pet.fitness_started_on,
        "last_step_settlement_date": pet.last_step_settlement_date,
        "last_sleep_settlement_date": pet.last_sleep_settlement_date,
    }
