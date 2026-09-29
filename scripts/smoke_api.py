"""Exercise real HTTP/JWT and clean up its own account afterward."""

import argparse
import uuid

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
        assert before["inventory"]["food"] == 1
        op.update(id=str(uuid.uuid4()), kind="feed", payload={})
        response = client.post("/api/actions/", json=op)
        response.raise_for_status()
        result = response.json()
        assert result["inventory"]["food"] == 0 and result["pet"]["hunger"] == 100
        refresh = client.post("/api/auth/refresh/", json={"refresh": tokens["refresh"]})
        refresh.raise_for_status()
        client.headers["Authorization"] = "Bearer " + refresh.json()["access"]
        old = client.post("/api/auth/refresh/", json={"refresh": tokens["refresh"]})
        assert old.status_code == 401
        client.post("/api/pet/chat/", json={"message": "你好"}).raise_for_status()
        print(
            "PASS: real HTTP register/login token, reward retry, feed, token rotation, AI fallback/demo"
        )
    finally:
        deleted = client.delete("/api/account/")
        deleted.raise_for_status()
        print("Smoke account deleted.")
