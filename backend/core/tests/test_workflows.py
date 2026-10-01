import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from core.models import InventoryItem, Pet, Profile, Session
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


@pytest.mark.parametrize("path", ["/api/pet/chat/", "/api/memories/", "/api/memories/1/", "/api/diary/"])
def test_removed_features_are_not_available(client, path):
    assert client.get(path).status_code == 404
    assert client.post(path, {}, format="json").status_code == 404


def test_reminder_quiet_hours(client):
    from core.jobs import generate_reminders
    user = get_user_model().objects.get(username="workflow")
    Profile.objects.filter(user=user).update(quiet_start=0, quiet_end=0)
    assert generate_reminders(user) == []


def test_care_actions_do_not_call_ai(client, monkeypatch):
    from core import ai
    def unexpected(*args, **kwargs):
        raise AssertionError("Care actions must not call an AI provider")
    monkeypatch.setattr(ai, "completion", unexpected)
    monkeypatch.setattr(ai, "embed", unexpected)
    for kind in ("water", "rest"):
        data = {"id": str(uuid.uuid4()), "generation": 1, "kind": kind, "payload": {}}
        assert client.post("/api/actions/", data, format="json").status_code == 200
    assert client.get("/api/today/").status_code == 200


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
    InventoryItem.objects.create(user=user, item_id=3, quantity=1)
    Pet.objects.filter(user=user).update(hunger=10)

    def run(_):
        close_old_connections()
        try:
            apply_action(user, {"id": uuid.uuid4(), "generation": 1, "kind": "use_item", "payload": {"item_id": 3}})
            return "ok"
        except Exception as exc:
            return getattr(exc, "status_code", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(map(str, results)) == ["409", "ok"]
    assert InventoryItem.objects.get(user=user, item_id=3).quantity == 0
    assert Pet.objects.get(user=user).hunger == 45


def test_focus_sessions_and_retired_walk_actions(client):
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
    assert action("walk_start").status_code == 400
    assert action("walk_finish").status_code == 400


def test_unavailable_steps_are_not_reported_as_a_known_zero(client):
    client.post("/api/health/sync/", {"steps": 5432}, format="json")
    r = client.post("/api/health/sync/", {"steps": None, "sleep_minutes": 420}, format="json")
    assert r.status_code == 200
    assert r.data["health"]["steps_observed_at"] is None
    assert r.data["health"]["step_delta_preview"] is None
    assert r.data["pet"]["fitness"] == 50


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


def test_legacy_walk_sessions_can_still_be_cancelled(client):
    user = get_user_model().objects.get(username="workflow")
    session = Session.objects.create(user=user, kind="walk", start_steps=0)
    assert client.get("/api/today/").data["sessions"] == []
    assert client.delete(f"/api/sessions/{session.pk}/").status_code == 204


def test_api_invalid_action_body_returns_400(client):
    assert client.post("/api/actions/", [], format="json").status_code == 400


def test_sleep_only_sync_does_not_claim_known_steps(client):
    result = client.post("/api/health/sync/", {"sleep_minutes": 400}, format="json")
    assert result.data["health"]["steps_observed_at"] is None
    assert result.data["health"]["step_delta_preview"] is None


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


def test_free_play_is_rejected_without_changing_mood_or_xp(client):
    before = Pet.objects.get()
    response = client.post('/api/actions/', {
        'id': str(uuid.uuid4()), 'generation': 1, 'kind': 'play', 'payload': {},
    }, format='json')
    assert response.status_code == 400
    after = Pet.objects.get()
    assert (after.mood, after.xp) == (before.mood, before.xp)
