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
            "quiet_start",
            "quiet_end",
        ]


class ActionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(
        choices=[
            "feed",
            "use_item",
            "claim_reward",
            "rest",
            "wake",
            "water",
            "complete",
            "progress",
            "rebirth",
            "focus_start",
            "focus_finish",
        ]
    )
    generation = serializers.IntegerField(min_value=1)
    occurred_at = serializers.DateTimeField(required=False)
    payload = serializers.DictField(default=dict)


class FitnessDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    steps = serializers.IntegerField(min_value=0, max_value=200000, allow_null=True, required=False)
    sleep_minutes = serializers.IntegerField(min_value=0, max_value=1080, allow_null=True, required=False)

    def validate(self, data):
        if "steps" not in data and "sleep_minutes" not in data:
            raise serializers.ValidationError("Include steps or sleep_minutes")
        return data


class HealthSerializer(serializers.Serializer):
    generation = serializers.IntegerField(min_value=1, required=False)
    days = FitnessDaySerializer(many=True, required=False, max_length=15)
    # Older clients may submit today's preview; never treat it as a completed day.
    steps = serializers.IntegerField(min_value=0, max_value=200000, allow_null=True, required=False)
    sleep_minutes = serializers.IntegerField(min_value=0, max_value=1080, allow_null=True, required=False)
    observed_at = serializers.DateTimeField(required=False)

    def validate(self, data):
        if "days" in data:
            if "generation" not in data:
                raise serializers.ValidationError("generation is required for historical health sync")
            dates = [item["date"] for item in data["days"]]
            if len(dates) != len(set(dates)):
                raise serializers.ValidationError("Duplicate health dates")
        return data


class PetDetailsSerializer(serializers.Serializer):
    generation = serializers.IntegerField(min_value=1)
    name = serializers.CharField(min_length=1, max_length=40, required=False, trim_whitespace=True)
    species = serializers.ChoiceField(choices=["potato", "cat"], required=False)
    personality = serializers.ChoiceField(choices=["gentle", "playful", "tsundere", "energetic", "calm"], required=False)

    def validate(self, data):
        if "initial_age_days" in self.initial_data or "gender" in self.initial_data:
            raise serializers.ValidationError("Age is automatic; gender is no longer editable")
        return data
