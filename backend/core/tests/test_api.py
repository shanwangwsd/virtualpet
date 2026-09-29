import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    u = get_user_model().objects.create_user("alice", password="GoodPassword123!")
    c = APIClient()
    c.force_authenticate(u)
    return c


def act(c, kind, **payload):
    return c.post(
        "/api/actions/",
        {"id": str(uuid.uuid4()), "kind": kind, "generation": 1, "payload": payload},
        format="json",
    )


def habit(c):
    r = c.post(
        "/api/habits/",
        {
            "name": "Japanese",
            "category": "study",
            "target": 30,
            "unit": "minutes",
            "reward_type": "food",
            "reward_amount": 1,
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    return r.data["id"]


def test_auth_required_and_today_initializes_pet(client):
    assert APIClient().get("/api/today/").status_code == 401
    r = client.get("/api/today/")
    assert r.status_code == 200
    assert r.data["pet"]["hunger"] == 70
    assert r.data["inventory"]["food"] == 0


def test_complete_then_feed_and_retry_idempotency(client):
    hid = habit(client)
    body = {
        "id": str(uuid.uuid4()),
        "kind": "complete",
        "generation": 1,
        "payload": {"habit_id": hid},
    }
    assert client.post("/api/actions/", body, format="json").status_code == 200
    assert client.post("/api/actions/", body, format="json").status_code == 200
    assert act(client, "complete", habit_id=hid).status_code == 200
    assert client.get("/api/today/").data["inventory"]["food"] == 1
    assert act(client, "feed").status_code == 200
    today = client.get("/api/today/").data
    assert today["inventory"]["food"] == 0
    assert today["pet"]["hunger"] == 100
    assert act(client, "feed").status_code == 409


def test_reused_operation_id_cannot_change_payload(client):
    body = {"id": str(uuid.uuid4()), "kind": "water", "generation": 1, "payload": {}}
    assert client.post("/api/actions/", body, format="json").status_code == 200
    body["kind"] = "feed"
    assert client.post("/api/actions/", body, format="json").status_code == 409


def test_habit_ownership_and_validation(client):
    hid = habit(client)
    other = APIClient()
    other.force_authenticate(get_user_model().objects.create_user("bob"))
    assert act(other, "complete", habit_id=hid).status_code == 404
    assert other.patch(f"/api/habits/{hid}/", {"name": "stolen"}, format="json").status_code == 404
    assert act(client, "progress", habit_id=hid, amount=-1).status_code == 400
    assert (
        client.post("/api/habits/", {"name": "bad", "target": 0}, format="json").status_code == 400
    )


def test_steps_only_award_delta_and_unknown_sleep_preserved(client):
    for steps in (2100, 5000, 5500):
        r = client.post("/api/health/sync/", {"steps": steps, "sleep_minutes": None}, format="json")
        assert r.status_code == 200
    today = client.get("/api/today/").data
    assert today["health"]["step_reward"] == 10
    assert today["pet"]["energy"] == 70
    assert today["health"]["sleep_minutes"] is None


def test_stale_health_and_future_actions_rejected(client):
    r = client.post(
        "/api/health/sync/",
        {"steps": 42, "observed_at": (timezone.now() - timedelta(days=1)).isoformat()},
        format="json",
    )
    assert r.status_code == 400
    r = client.post(
        "/api/actions/",
        {
            "id": str(uuid.uuid4()),
            "kind": "water",
            "generation": 1,
            "occurred_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "payload": {},
        },
        format="json",
    )
    assert r.status_code == 400


def test_water_rewards_are_capped(client):
    for _ in range(8):
        assert act(client, "water").status_code == 200
    t = client.get("/api/today/").data
    assert t["water_count"] == 8
    assert t["pet"]["hydration"] == 100


def test_logout_and_delete_account(client):
    assert client.delete("/api/account/").status_code == 204
    assert not get_user_model().objects.filter(username="alice").exists()
