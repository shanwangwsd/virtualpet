from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from . import ai, services
from .models import Diary, Profile, Reminder


def diary(user):
    state = services.today(user)
    day = state["date"]
    existing = Diary.objects.filter(user=user, date=day).first()
    if existing:
        return existing
    response = ai.respond(user, "请总结今天的习惯，写一条简短的宠物日记。")
    # Keep a compact snapshot. Raw health samples never reach the backend.
    summary = {
        "habits": state["habits"],
        "health": state["health"],
        "pet": {"level": state["pet"]["level"], "generation": state["pet"]["generation"]},
    }
    import json

    from rest_framework.renderers import JSONRenderer

    summary = json.loads(JSONRenderer().render(summary))
    with transaction.atomic():
        services.lock_owner(user)
        obj, _ = Diary.objects.get_or_create(
            user=user, date=day, defaults={"summary": summary, "response": response}
        )
    return obj


def generate_reminders(user):
    state = services.today(user)
    profile = Profile.objects.get(user=user)
    hour = timezone.now().astimezone(ZoneInfo(profile.timezone)).hour
    start, end = profile.quiet_start, profile.quiet_end
    quiet = (start == end) or (start <= hour < end if start < end else hour >= start or hour < end)
    if quiet or state["pet"]["state"] == "dead":
        return []
    reasons = []
    if state["pet"]["hunger"] < 40:
        reasons.append("hunger")
    if hour >= 18 and any(not h["completed"] for h in state["habits"]):
        reasons.append("habit")
    if 12 <= hour <= 20 and state["water_count"] < 3:
        reasons.append("water")
    created = []
    for reason in reasons:
        if Reminder.objects.filter(user=user, date=state["date"], reason=reason).exists():
            continue
        response = ai.respond(user, f"Generate a gentle reminder: {reason}.")
        with transaction.atomic():
            services.lock_owner(user)
            if Reminder.objects.filter(user=user, date=state["date"]).count() >= 3:
                break
            obj, new = Reminder.objects.get_or_create(
                user=user, date=state["date"], reason=reason, defaults={"response": response}
            )
            if new:
                created.append(obj)
    return created
