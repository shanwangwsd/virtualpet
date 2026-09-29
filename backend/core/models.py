from django.conf import settings
from django.db import models
from django.utils import timezone
from pgvector.django import VectorField


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=64, default="Asia/Tokyo")
    personality = models.CharField(max_length=20, default="playful")
    sleep_target = models.PositiveIntegerField(default=480)
    ai_health_consent = models.BooleanField(default=False)
    memory_enabled = models.BooleanField(default=False)
    quiet_start = models.PositiveSmallIntegerField(default=22)
    quiet_end = models.PositiveSmallIntegerField(default=8)


class Pet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=40, default="Mochi")
    generation = models.PositiveIntegerField(default=1)
    hunger = models.PositiveIntegerField(default=70)
    hydration = models.PositiveIntegerField(default=70)
    energy = models.PositiveIntegerField(default=70)
    bond = models.PositiveIntegerField(default=10)
    xp = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    state = models.CharField(max_length=20, default="healthy")
    study_score = models.PositiveIntegerField(default=0)
    activity_score = models.PositiveIntegerField(default=0)
    completed_habits = models.PositiveIntegerField(default=0)
    born_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    critical_since = models.DateTimeField(null=True, blank=True)
    died_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "generation"], name="unique_generation")
        ]


class Inventory(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    food = models.PositiveIntegerField(default=0)
    coin = models.PositiveIntegerField(default=0)


class Habit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=20, default="study")
    target = models.PositiveIntegerField(default=30)
    unit = models.CharField(max_length=20, default="minutes")
    frequency = models.CharField(max_length=10, default="daily")
    reward_type = models.CharField(max_length=10, default="food")
    reward_amount = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)


class HabitLog(models.Model):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE)
    date = models.DateField()
    progress = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    reward_claimed = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["habit", "date"], name="unique_habit_day")]


class Daily(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    steps = models.PositiveIntegerField(default=0)
    sleep_minutes = models.PositiveIntegerField(null=True, blank=True)
    health_observed_at = models.DateTimeField(null=True, blank=True)
    steps_observed_at = models.DateTimeField(null=True, blank=True)
    step_reward = models.PositiveIntegerField(default=0)
    water_count = models.PositiveIntegerField(default=0)
    play_count = models.PositiveIntegerField(default=0)
    fed = models.BooleanField(default=False)
    walked = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="unique_user_day")]


class Action(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    operation_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    kind = models.CharField(max_length=30)
    generation = models.PositiveIntegerField()
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    result = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "operation_id"], name="unique_user_operation")
        ]


class RewardLedger(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=100)
    resource = models.CharField(max_length=10)
    amount = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source", "resource"], name="unique_reward_source"
            )
        ]


class Session(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=10)
    habit = models.ForeignKey(Habit, on_delete=models.SET_NULL, null=True)
    start_steps = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind"],
                condition=models.Q(ended_at__isnull=True),
                name="one_active_session_kind",
            )
        ]


class Interaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.CharField(max_length=1000)
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class Memory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.CharField(max_length=500)
    category = models.CharField(max_length=30, default="preference")
    importance = models.FloatField(default=0.7)
    source = models.CharField(max_length=30, default="explicit")
    source_id = models.PositiveBigIntegerField(null=True)
    embedding = VectorField(dimensions=1536, null=True)
    embedding_model = models.CharField(max_length=120, default="demo-hash-v1")
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "content"], name="unique_memory_content")
        ]


class Diary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    summary = models.JSONField(default=dict)
    response = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="unique_diary_day")]


class Reminder(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    reason = models.CharField(max_length=30)
    response = models.JSONField(default=dict)
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "reason"], name="unique_reminder_reason"
            )
        ]


class Device(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=256, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)


class PushDelivery(models.Model):
    reminder = models.ForeignKey(Reminder, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    attempts = models.PositiveSmallIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)
    retry_after = models.DateTimeField(default=timezone.now)
    last_status = models.IntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reminder", "device"], name="unique_push_delivery")
        ]
