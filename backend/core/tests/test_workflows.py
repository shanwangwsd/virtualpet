import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from core.models import Inventory, Pet, Profile, Session
from core.services import apply_action, today
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def client(db):
    u = get_user_model().objects.create_user("workflow", password="VeryGoodPassword123!")
    c = APIClient()
    c.force_authenticate(u)
    today(u)
    return c


def test_chat_memory_consent_and_deletion(client):
    assert (
        client.post("/api/pet/chat/", {"message": "记住：我喜欢日语"}, format="json").status_code
        == 200
    )
    assert client.get("/api/memories/").data == []
    client.patch("/api/profile/", {"memory_enabled": True}, format="json")
    assert (
        client.post("/api/pet/chat/", {"message": "记住：我喜欢日语"}, format="json").status_code
        == 200
    )
    memories = client.get("/api/memories/").data
    assert len(memories) == 1
    assert client.delete(f"/api/memories/{memories[0]['id']}/").status_code == 204
    assert client.get("/api/memories/").data == []


def test_diary_idempotency_and_reminder_quiet_hours(client):
    a = client.post("/api/diary/", {}, format="json")
    b = client.post("/api/diary/", {}, format="json")
    assert a.status_code == 200
    assert a.data["id"] == b.data["id"]
    from core.jobs import generate_reminders

    user = get_user_model().objects.get(username="workflow")
    Profile.objects.filter(user=user).update(quiet_start=0, quiet_end=0)
    assert generate_reminders(user) == []  # equal hours means all-day quiet


def test_rebirth_keeps_history_rejects_old_generation(client):
    Pet.objects.update(
        state="dead", critical_since=timezone.now() - timedelta(days=3), died_at=timezone.now()
    )
    payload = {"id": str(uuid.uuid4()), "generation": 1, "kind": "rebirth", "payload": {}}
    r = client.post("/api/actions/", payload, format="json")
    assert r.status_code == 200 and r.data["pet"]["generation"] == 2
    payload.update(id=str(uuid.uuid4()), kind="water")
    assert client.post("/api/actions/", payload, format="json").status_code == 409
    assert len(client.get("/api/pet/generations/").data) == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_feed_spends_inventory_once():
    user = get_user_model().objects.create_user("parallel")
    today(user)
    Inventory.objects.filter(user=user).update(food=1)
    Pet.objects.filter(user=user).update(hunger=10)

    def run(_):
        close_old_connections()
        try:
            apply_action(user, {"id": uuid.uuid4(), "generation": 1, "kind": "feed", "payload": {}})
            return "ok"
        except Exception as exc:
            return getattr(exc, "status_code", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(map(str, results)) == ["409", "ok"]
    assert Inventory.objects.get(user=user).food == 0
    assert Pet.objects.get(user=user).hunger == 40


def test_focus_and_walk_sessions(client):
    h = client.post("/api/habits/", {"name": "Read", "target": 1}, format="json").data["id"]

    def action(kind, **payload):
        return client.post(
            "/api/actions/",
            {"id": str(uuid.uuid4()), "kind": kind, "generation": 1, "payload": payload},
            format="json",
        )

    assert action("focus_start", habit_id=h).status_code == 200
    assert action("focus_finish").status_code == 409
    Session.objects.update(started_at=timezone.now() - timedelta(minutes=2))
    assert action("focus_finish").status_code == 200
    client.post("/api/health/sync/", {"steps": 0}, format="json")
    assert action("walk_start").status_code == 200
    client.post("/api/health/sync/", {"steps": 1100}, format="json")
    assert action("walk_finish").status_code == 200
    assert action("walk_start").status_code == 409


def test_missing_steps_does_not_erase_previous_summary(client):
    client.post("/api/health/sync/", {"steps": 5432}, format="json")
    r = client.post("/api/health/sync/", {"steps": None, "sleep_minutes": 420}, format="json")
    assert r.status_code == 200
    assert r.data["health"]["steps"] == 5432
    assert r.data["pet"]["energy"] == 87


def test_live_candidate_requires_exact_supporting_quote():
    from core.ai import validate_candidate

    assert (
        validate_candidate(
            {
                "content": "User studies Japanese",
                "category": "routine",
                "importance": 0.8,
                "evidence": "studies Japanese",
            },
            "hello",
        )
        is None
    )
    good = validate_candidate(
        {
            "content": "I study Japanese after dinner",
            "category": "routine",
            "importance": 0.8,
            "evidence": "I study Japanese after dinner",
        },
        "I study Japanese after dinner",
    )
    assert good["source"] == "user_statement"


def test_device_registration_validation_and_isolation(client):
    assert client.post("/api/devices/", {"token": "not-valid"}, format="json").status_code == 400
    token = "ab" * 32
    assert client.post("/api/devices/", {"token": token}, format="json").status_code == 201
    assert client.delete("/api/devices/", {"token": token}, format="json").status_code == 204


def test_walk_requires_fresh_health_baseline_and_old_session_can_cancel(client):
    payload = {"id": str(uuid.uuid4()), "kind": "walk_start", "generation": 1, "payload": {}}
    assert client.post("/api/actions/", payload, format="json").status_code == 409
    client.post("/api/health/sync/", {"steps": 2500}, format="json")
    assert client.post("/api/actions/", payload, format="json").status_code == 200
    session = Session.objects.get(kind="walk")
    Session.objects.filter(pk=session.pk).update(started_at=timezone.now() - timedelta(days=1))
    assert client.delete(f"/api/sessions/{session.pk}/").status_code == 204
    payload["id"] = str(uuid.uuid4())
    assert client.post("/api/actions/", payload, format="json").status_code == 200


def test_api_invalid_body_and_category_return_400(client):
    assert client.post("/api/pet/chat/", [], format="json").status_code == 400
    client.patch("/api/profile/", {"memory_enabled": True}, format="json")
    assert (
        client.post(
            "/api/memories/", {"content": "hello", "category": {}}, format="json"
        ).status_code
        == 400
    )


def test_sleep_only_sync_does_not_make_stale_steps_fresh(client):
    client.post("/api/health/sync/", {"sleep_minutes": 400}, format="json")
    r = client.post(
        "/api/actions/",
        {"id": str(uuid.uuid4()), "kind": "walk_start", "generation": 1, "payload": {}},
        format="json",
    )
    assert r.status_code == 409


def test_health_consent_revocation_excludes_prior_ai_health_reply(client):
    from core.ai import build_context
    from core.models import Interaction

    user = get_user_model().objects.get(username="workflow")
    Interaction.objects.create(
        user=user, text="Hello", response={"message": "You slept 5 hours last night"}
    )
    context = build_context(user, "Hello again", "recent")
    assert "5 hours" not in str(context)


def test_push_retry_and_delivered_record_are_idempotent(client, monkeypatch):
    from zoneinfo import ZoneInfo

    from core.models import Device, PushDelivery, Reminder
    from core.push import deliver_pending

    user = get_user_model().objects.get(username="workflow")
    profile = Profile.objects.get(user=user)
    now = timezone.now().astimezone(ZoneInfo(profile.timezone))
    Profile.objects.filter(user=user).update(
        quiet_start=(now.hour + 1) % 24, quiet_end=(now.hour + 2) % 24
    )
    Device.objects.create(user=user, token="ab" * 32)
    Reminder.objects.create(
        user=user, date=now.date(), reason="habit", response={"message": "A small step"}
    )
    monkeypatch.setattr("core.push.configured", lambda: True)
    monkeypatch.setattr("core.push.send", lambda *args: 503)
    assert deliver_pending() == 0
    delivery = PushDelivery.objects.get()
    assert delivery.attempts == 1 and delivery.delivered_at is None
    assert deliver_pending() == 0
    delivery.refresh_from_db()
    assert delivery.attempts == 1
    PushDelivery.objects.update(retry_after=timezone.now() - timedelta(minutes=1))
    monkeypatch.setattr("core.push.send", lambda *args: 200)
    assert deliver_pending() == 1
    assert deliver_pending() == 0
    delivery.refresh_from_db()
    assert delivery.attempts == 2 and delivery.delivered_at is not None
