import logging

import httpx
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from . import ai, jobs, services
from .models import Diary, Interaction, Memory, Profile, Reminder


class AIThrottle(UserRateThrottle):
    scope = "ai"


@api_view(["POST"])
@throttle_classes([AIThrottle])
def chat(request):
    message = request.data.get("message")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 1000:
        raise ValidationError("Message must contain 1–1000 characters")
    response = ai.respond(request.user, message)
    interaction = Interaction.objects.create(user=request.user, text=message, response=response)
    profile = Profile.objects.get(user=request.user)
    candidate = None
    if profile.memory_enabled:
        try:
            candidate = ai.extract_with_model(message)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            logging.getLogger(__name__).warning("memory_extraction_failed")
    response = dict(response)
    response["memory_status"] = "not_requested"
    if candidate:
        try:
            ai.save_memory(request.user, **candidate, source_id=interaction.id)
            response["memory_status"] = "saved"
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logging.getLogger(__name__).warning("memory_failed type=%s", type(exc).__name__)
            response["memory_status"] = "failed"
    return Response(response)


@api_view(["GET", "POST"])
def memories(request):
    if request.method == "POST":
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if not profile.memory_enabled:
            raise ValidationError("Enable memory in settings first")
        content = request.data.get("content", "")
        category = request.data.get("category", "preference")
        if (
            not isinstance(content, str)
            or not isinstance(category, str)
            or category not in ai.CATEGORIES
        ):
            raise ValidationError("Invalid memory")
        try:
            obj = ai.save_memory(request.user, content, category)
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response({"id": obj.id, "content": obj.content}, status=201)
    return Response(
        list(
            Memory.objects.filter(user=request.user)
            .order_by("-created_at")
            .values(
                "id", "content", "category", "importance", "source", "created_at", "last_used_at"
            )[:200]
        )
    )


@api_view(["DELETE"])
def memory_detail(request, pk):
    get_object_or_404(Memory, user=request.user, pk=pk).delete()
    return Response(status=204)


@api_view(["GET", "POST"])
@throttle_classes([AIThrottle])
def diary(request):
    if request.method == "POST":
        obj = jobs.diary(request.user)
        return Response(
            {"id": obj.id, "date": obj.date, "summary": obj.summary, "response": obj.response}
        )
    return Response(
        list(
            Diary.objects.filter(user=request.user)
            .order_by("-date")
            .values("id", "date", "summary", "response")[:30]
        )
    )


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
