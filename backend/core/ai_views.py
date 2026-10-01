from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from . import services
from .models import Action, Profile, Reminder


@api_view(["GET"])
def reminders(request):
    services.today(request.user)
    from zoneinfo import ZoneInfo

    from django.utils import timezone

    profile = Profile.objects.get(user=request.user)
    day = timezone.now().astimezone(ZoneInfo(profile.timezone)).date()
    return Response(
        list(
            Reminder.objects.filter(user=request.user, date=day, acknowledged=False).values(
                "id", "reason", "response", "created_at"
            )
        )
    )


@api_view(["POST"])
def acknowledge(request, pk):
    reminder = get_object_or_404(Reminder, user=request.user, pk=pk)
    reminder.acknowledged = True
    reminder.save(update_fields=["acknowledged"])
    return Response(status=204)


class ReactionThrottle(UserRateThrottle):
    scope = "ai"


@api_view(["POST"])
@throttle_classes([ReactionThrottle])
def reaction(request):
    import uuid

    from . import ai
    try:
        operation = uuid.UUID(str(request.data.get("action_id", "")))
    except ValueError:
        raise ValidationError("A completed care action is required")
    action = get_object_or_404(Action, user=request.user, operation_id=operation)
    if action.kind not in ("water", "use_item", "rest", "wake"):
        raise ValidationError("This action does not have a care reaction")
    current = services.today(request.user)
    if current["pet"]["generation"] != action.generation or current["pet"]["state"] == "dead":
        raise ValidationError("This pet is no longer active")
    profile = Profile.objects.get(user=request.user)
    key = f"reaction:{request.user.pk}:{operation}:{profile.personality}:{profile.ai_health_consent}"
    result = cache.get(key)
    if result is None:
        event = action.kind
        if action.kind == "use_item":
            from .catalog import ITEMS
            item = ITEMS.get(action.result.get("used_item_id"))
            if item is None:
                event = "used a care item"  # Old action snapshots did not store the item ID.
            else:
                event = f"used {item['category']} {item['name']}"
        result = ai.respond(request.user, f"React to my completed care action: {event}.", mode="none")
        cache.set(key, result, 3600)
    return Response(result)


@api_view(["POST"])
@throttle_classes([ReactionThrottle])
def schedule_speech(request):
    import httpx
    from rest_framework import serializers

    from . import ai

    class Input(serializers.Serializer):
        title = serializers.CharField(min_length=1, max_length=80, trim_whitespace=True)
        hour = serializers.IntegerField(min_value=0, max_value=23)
        minute = serializers.IntegerField(min_value=0, max_value=59)

    data = Input(data=request.data)
    data.is_valid(raise_exception=True)
    context = ai.build_context(request.user, "Write my pet's scheduled activity reminder.", mode="none")
    context["schedule"] = data.validated_data
    try:
        result = ai.generate(context)
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, IndexError):
        result = ai.fallback(context)
    return Response({**result, "personality": context["personality"]})
