from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from . import ai, services
from .models import Profile, Reminder


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
        response = ai.respond(user, f"Generate a gentle reminder: {reason}.", mode="none")
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
