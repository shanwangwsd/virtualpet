from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.jobs import generate_reminders


class Command(BaseCommand):
    help = "Run idempotent reminder jobs once; schedule every 15 minutes."

    def handle(self, *args, **options):
        count = 0
        for user in get_user_model().objects.filter(is_active=True).iterator():
            try:
                count += len(generate_reminders(user))
            except Exception as exc:
                self.stderr.write(f"user_id={user.id} failed: {type(exc).__name__}")
        from core.push import deliver_pending

        delivered = deliver_pending()
        self.stdout.write(f"APNs accepted {delivered} notification(s).")
        self.stdout.write(
            f"Created {count} reminder(s). Remote delivery requires APNs configuration; Schedule reminders run locally on Watch."
        )
