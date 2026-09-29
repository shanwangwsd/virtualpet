from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.jobs import diary, generate_reminders
from core.models import Profile


class Command(BaseCommand):
    help = "Run idempotent reminder and daily reflection jobs once; schedule every 15 minutes."

    def handle(self, *args, **options):
        count = 0
        for user in get_user_model().objects.filter(is_active=True).iterator():
            try:
                count += len(generate_reminders(user))
                profile = Profile.objects.get(user=user)
                if timezone.now().astimezone(ZoneInfo(profile.timezone)).hour >= 21:
                    diary(user)
            except Exception as exc:
                self.stderr.write(f"user_id={user.id} failed: {type(exc).__name__}")
        from core.push import deliver_pending

        delivered = deliver_pending()
        self.stdout.write(f"APNs accepted {delivered} notification(s).")
        self.stdout.write(
            f"Created {count} reminder(s). Watch fetches inbox when active; local notifications are scheduled on device."
        )
