from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import Habit, Pet, Profile, Session
from .serializers import (
    ActionSerializer,
    HabitSerializer,
    HealthSerializer,
    PetDetailsSerializer,
    ProfileSerializer,
)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    if (
        not isinstance(username, str)
        or not 3 <= len(username) <= 80
        or not username.isascii()
        or not all(c.isalnum() or c in "_-." for c in username)
    ):
        raise ValidationError("Username must be 3–80 ASCII letters, digits, _, - or .")
    if not isinstance(password, str) or len(password) > 128:
        raise ValidationError("Invalid password")
    user = get_user_model()(username=username)
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": exc.messages})
    try:
        with transaction.atomic():
            user.set_password(password)
            user.save()
    except IntegrityError:
        raise ValidationError("Username unavailable")
    token = RefreshToken.for_user(user)
    return Response(
        {"access": str(token.access_token), "refresh": str(token), "user_id": user.pk}, status=201
    )


@api_view(["GET"])
def today(request):
    return Response(services.today(request.user))


@api_view(["POST"])
def actions(request):
    serializer = ActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(services.apply_action(request.user, serializer.validated_data))


@api_view(["POST"])
def health(request):
    serializer = HealthSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(services.sync_health(request.user, serializer.validated_data))


class Habits(generics.ListCreateAPIView):
    serializer_class = HabitSerializer

    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user, active=True).order_by("id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class HabitDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = HabitSerializer

    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            services.lock_owner(self.request.user)
            serializer.save()

    def perform_destroy(self, instance):
        with transaction.atomic():
            services.lock_owner(self.request.user)
            instance.active = False
            instance.save()
            Session.objects.filter(habit=instance, ended_at__isnull=True).update(
                ended_at=timezone.now()
            )


@api_view(["GET", "PATCH"])
def profile(request):
    with transaction.atomic():
        services.lock_owner(request.user)
        obj, _ = Profile.objects.get_or_create(user=request.user)
        if request.method == "PATCH":
            serializer = ProfileSerializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(ProfileSerializer(obj).data)


@api_view(["DELETE"])
def account(request):
    with transaction.atomic():
        services.lock_owner(request.user)
        request.user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def generations(request):
    return Response(
        list(
            Pet.objects.filter(user=request.user)
            .order_by("-generation")
            .values(
                "id",
                "name",
                "generation",
                "level",
                "xp",
                "bond",
                "born_at",
                "died_at",
                "completed_habits",
                "study_score",
                "activity_score",
                "state",
            )
        )
    )


@api_view(["DELETE"])
def cancel_session(request, pk):
    with transaction.atomic():
        services.lock_owner(request.user)
        session = get_object_or_404(Session, pk=pk, user=request.user)
        session.ended_at = timezone.now()
        session.save()
    return Response(status=204)


@api_view(["GET"])
@permission_classes([AllowAny])
def healthcheck(request):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok"})


@api_view(["POST", "DELETE"])
def devices(request):
    import re

    from .models import Device

    token = request.data.get("token", "")
    if (
        not isinstance(token, str)
        or not re.fullmatch(r"[0-9a-fA-F]{64,256}", token)
        or len(token) % 2
    ):
        raise ValidationError("Expected a hexadecimal APNs device token")
    token = token.lower()
    if request.method == "DELETE":
        Device.objects.filter(user=request.user, token=token).delete()
        return Response(status=204)
    # Transfer of a device token to another account invalidates old queued deliveries.
    with transaction.atomic():
        Device.objects.filter(token=token).exclude(user=request.user).delete()
        Device.objects.update_or_create(
            token=token, defaults={"user": request.user, "active": True}
        )
    return Response({"registered": True}, status=201)


@api_view(["PATCH"])
def pet_details(request):
    serializer = PetDetailsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(services.update_pet_details(request.user, serializer.validated_data))
