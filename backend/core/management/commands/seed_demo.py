import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Habit
from core.services import today


class Command(BaseCommand):
    help = (
        "Create a local demo account without hard-coded passwords; never overwrite existing users."
    )

    def handle(self, *args, **options):
        user, created = get_user_model().objects.get_or_create(username="demo")
        if created:
            password = secrets.token_urlsafe(14)
            user.set_password(password)
            user.save()
            self.stdout.write(
                f"Username: demo\nPassword: {password}\nSave locally; not committed to source control."
            )
        else:
            self.stdout.write(
                "Demo exists. Use changepassword demo if you need to reset the password."
            )
        today(user)
        for name, category, target, unit in [
            ("Japanese study", "study", 30, "minutes"),
            ("Reading", "reading", 20, "minutes"),
            ("Stretch", "exercise", 1, "session"),
        ]:
            Habit.objects.get_or_create(
                user=user,
                name=name,
                defaults={"category": category, "target": target, "unit": unit},
            )
