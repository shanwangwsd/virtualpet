from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from .models import Habit, Profile


class HabitSerializer(serializers.ModelSerializer):
    target = serializers.IntegerField(min_value=1, max_value=10000, default=30)
    reward_amount = serializers.IntegerField(min_value=1, max_value=100, default=1)
    category = serializers.ChoiceField(
        choices=["study", "work", "reading", "exercise", "custom"], default="study"
    )
    reward_type = serializers.ChoiceField(choices=["food", "xp", "coin"], default="food")
    frequency = serializers.ChoiceField(choices=["daily"], default="daily")

    class Meta:
        model = Habit
        fields = [
            "id",
            "name",
            "category",
            "target",
            "unit",
            "frequency",
            "reward_type",
            "reward_amount",
            "active",
        ]
        read_only_fields = ["id"]


class ProfileSerializer(serializers.ModelSerializer):
    sleep_target = serializers.IntegerField(min_value=240, max_value=720)
    quiet_start = serializers.IntegerField(min_value=0, max_value=23)
    quiet_end = serializers.IntegerField(min_value=0, max_value=23)
    personality = serializers.ChoiceField(
        choices=["gentle", "playful", "tsundere", "energetic", "calm"]
    )

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise serializers.ValidationError("Unknown IANA timezone")
        return value

    class Meta:
        model = Profile
        fields = [
            "timezone",
            "personality",
            "sleep_target",
            "ai_health_consent",
            "memory_enabled",
            "quiet_start",
            "quiet_end",
        ]


class ActionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(
        choices=[
            "feed",
            "water",
            "play",
            "complete",
            "progress",
            "rebirth",
            "walk_start",
            "walk_finish",
            "focus_start",
            "focus_finish",
        ]
    )
    generation = serializers.IntegerField(min_value=1)
    occurred_at = serializers.DateTimeField(required=False)
    payload = serializers.DictField(default=dict)


class HealthSerializer(serializers.Serializer):
    steps = serializers.IntegerField(min_value=0, max_value=200000, allow_null=True, required=False)
    sleep_minutes = serializers.IntegerField(
        min_value=0, max_value=1440, allow_null=True, required=False
    )
    observed_at = serializers.DateTimeField(required=False)
