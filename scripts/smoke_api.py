"""Exercise real HTTP/JWT and clean up its own account afterward."""

import argparse
import uuid
from datetime import datetime, timezone

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000")
args = parser.parse_args()
with httpx.Client(base_url=args.url, timeout=20) as client:
    credentials = {
        "username": "smoke_" + uuid.uuid4().hex[:16],
        "password": uuid.uuid4().hex + "Aa!",
    }
    response = client.post("/api/auth/register/", json=credentials)
    response.raise_for_status()
    tokens = response.json()
    client.headers["Authorization"] = "Bearer " + tokens["access"]
    try:
        login = client.post("/api/auth/login/", json=credentials)
        login.raise_for_status()
        tokens = login.json()
        client.headers["Authorization"] = "Bearer " + tokens["access"]
        response = client.post("/api/habits/", json={"name": "Smoke study", "target": 30})
        response.raise_for_status()
        habit = response.json()
        op = {
            "id": str(uuid.uuid4()),
            "generation": 1,
            "kind": "complete",
            "payload": {"habit_id": habit["id"]},
        }
        for _ in range(2):
            client.post("/api/actions/", json=op).raise_for_status()
        before = client.get("/api/today/").json()
        assert before["inventory"]["food"] == 0
        reward = before["pending_rewards"][0]["id"]
        op.update(id=str(uuid.uuid4()), kind="claim_reward", payload={"reward_id": reward, "category": 0})
        claim = client.post("/api/actions/", json=op)
        claim.raise_for_status()
        item = claim.json()["inventory"]["items"][0]
        op.update(id=str(uuid.uuid4()), kind="use_item", payload={"item_id": item["id"]})
        response = client.post("/api/actions/", json=op)
        response.raise_for_status()
        result = response.json()
        assert result["inventory"]["food"] == 0 and result["pet"]["hunger"] == min(100, 70 + item["effect"])
        assert result["pet"]["fitness"] == 50
        health = {
            "generation": result["pet"]["generation"],
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "days": [{"date": result["health"]["fitness_started_on"], "steps": 5000, "sleep_minutes": None}],
        }
        for _ in range(2):
            synced = client.post("/api/health/sync/", json=health)
            synced.raise_for_status()
            assert synced.json()["pet"]["fitness"] == 50
            assert synced.json()["health"]["step_delta_preview"] == 30
        op.update(id=str(uuid.uuid4()), kind="walk_start", payload={})
        assert client.post("/api/actions/", json=op).status_code == 400
        refresh = client.post("/api/auth/refresh/", json={"refresh": tokens["refresh"]})
        refresh.raise_for_status()
        client.headers["Authorization"] = "Bearer " + refresh.json()["access"]
        old = client.post("/api/auth/refresh/", json={"refresh": tokens["refresh"]})
        assert old.status_code == 401
        assert client.post("/api/pet/chat/", json={"message": "Hello"}).status_code == 404
        logout = client.post("/api/auth/logout/", json={"refresh": refresh.json()["refresh"]})
        logout.raise_for_status()
        assert client.post("/api/auth/refresh/", json={"refresh": refresh.json()["refresh"]}).status_code == 401
        print(
            "PASS: real HTTP register/login token, reward retry, feed, token rotation/revocation, Fitness preview/retry, removed Walk and chat"
        )
    finally:
        deleted = client.delete("/api/account/")
        deleted.raise_for_status()
        print("Smoke account deleted.")
