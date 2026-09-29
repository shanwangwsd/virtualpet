"""Optional APNs delivery. Missing credentials leave reminders in the in-app inbox."""

import os
import time
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import jwt
from django.db import transaction
from django.utils import timezone

from .models import Device, Profile, PushDelivery, Reminder


def configured():
    return all(
        os.getenv(key) for key in ("APNS_KEY_PATH", "APNS_KEY_ID", "APNS_TEAM_ID", "APNS_TOPIC")
    )


def send(device_token, message, collapse_id):
    token = jwt.encode(
        {"iss": os.environ["APNS_TEAM_ID"], "iat": int(time.time())},
        Path(os.environ["APNS_KEY_PATH"]).read_text(),
        algorithm="ES256",
        headers={"kid": os.environ["APNS_KEY_ID"]},
    )
    host = (
        "https://api.sandbox.push.apple.com"
        if os.getenv("APNS_SANDBOX", "1") == "1"
        else "https://api.push.apple.com"
    )
    headers = {
        "authorization": "bearer " + token,
        "apns-topic": os.environ["APNS_TOPIC"],
        "apns-push-type": "alert",
        "apns-priority": "10",
        "apns-collapse-id": collapse_id,
        "apns-expiration": str(int(time.time()) + 3600),
    }
    with httpx.Client(http2=True, timeout=10) as client:
        result = client.post(
            host + "/3/device/" + device_token,
            headers=headers,
            json={"aps": {"alert": {"title": "Mochi", "body": message}, "sound": "default"}},
        )
    return result.status_code


def deliver_pending():
    if not configured():
        return 0
    now = timezone.now()
    for reminder in Reminder.objects.filter(
        created_at__gte=now - timedelta(hours=12), acknowledged=False
    ):
        profile = Profile.objects.get(user=reminder.user)
        local = now.astimezone(ZoneInfo(profile.timezone))
        start, end = profile.quiet_start, profile.quiet_end
        quiet = start == end or (
            start <= local.hour < end if start < end else local.hour >= start or local.hour < end
        )
        if quiet or reminder.date != local.date():
            continue
        for device in Device.objects.filter(user=reminder.user, active=True):
            PushDelivery.objects.get_or_create(reminder=reminder, device=device)
    delivered = 0
    for pk in PushDelivery.objects.filter(
        delivered_at__isnull=True,
        attempts__lt=5,
        retry_after__lte=timezone.now(),
        device__active=True,
        reminder__created_at__gte=now - timedelta(hours=12),
    ).values_list("id", flat=True):
        with transaction.atomic():
            item = (
                PushDelivery.objects.select_for_update()
                .select_related("device", "reminder")
                .get(pk=pk)
            )
            if (
                item.delivered_at
                or item.retry_after > timezone.now()
                or item.device.user_id != item.reminder.user_id
            ):
                continue
            profile = Profile.objects.get(user=item.device.user)
            local = timezone.now().astimezone(ZoneInfo(profile.timezone))
            a, b = profile.quiet_start, profile.quiet_end
            if (
                item.reminder.acknowledged
                or item.reminder.date != local.date()
                or a == b
                or (a <= local.hour < b if a < b else local.hour >= a or local.hour < b)
            ):
                continue
            item.attempts += 1
            item.retry_after = timezone.now() + timedelta(minutes=2**item.attempts)
            item.save()
            # Lock prevents parallel workers sending the same record; HTTP timeout is bounded.
            try:
                code = send(
                    item.device.token,
                    item.reminder.response["message"],
                    f"reminder-{item.reminder_id}",
                )
            except (httpx.HTTPError, OSError, ValueError):
                code = 0
            item.last_status = code
            if code == 200:
                item.delivered_at = timezone.now()
                delivered += 1
            elif code in (400, 410):
                Device.objects.filter(pk=item.device_id).update(active=False)
            item.save()
    return delivered
