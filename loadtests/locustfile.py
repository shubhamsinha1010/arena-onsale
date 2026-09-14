"""Locust personas for queued fans vs the admitted sliver that actually books.

Install the optional load group, start the API, then:

    uv sync --group load
    uv run locust -f loadtests/locustfile.py --host http://127.0.0.1:8000
"""

from __future__ import annotations

import uuid

from locust import HttpUser, between, task


class WaitingFan(HttpUser):
    """Most users live in the waiting room and never touch inventory."""

    wait_time = between(0.2, 1.0)
    weight = 10

    def on_start(self) -> None:
        self.visitor_id = str(uuid.uuid4())
        self.token: str | None = None
        response = self.client.post(
            "/waiting-room/join", json={"visitor_id": self.visitor_id}, name="join"
        )
        if response.status_code == 200:
            body = response.json()
            if body.get("state") == "admitted":
                self.token = body.get("token")

    @task(8)
    def poll_queue(self) -> None:
        if self.token is not None:
            return
        response = self.client.get(
            f"/waiting-room/status/{self.visitor_id}", name="status"
        )
        if response.status_code == 200:
            body = response.json()
            if body.get("state") == "admitted":
                self.token = body.get("token")

    @task(1)
    def watch_stats(self) -> None:
        self.client.get("/waiting-room/stats", name="stats")


class AdmittedShopper(HttpUser):
    """One GA reserve + checkout per admitted user. 409 sold-out is success."""

    wait_time = between(0.5, 2.0)
    weight = 1

    def on_start(self) -> None:
        self.visitor_id = str(uuid.uuid4())
        self.token: str | None = None
        self.bought = False
        response = self.client.post(
            "/waiting-room/join", json={"visitor_id": self.visitor_id}, name="join"
        )
        if response.status_code == 200:
            body = response.json()
            if body.get("state") == "admitted":
                self.token = body.get("token")

    @task
    def shop(self) -> None:
        if not self.token:
            response = self.client.get(
                f"/waiting-room/status/{self.visitor_id}", name="status"
            )
            if response.status_code == 200:
                body = response.json()
                if body.get("state") == "admitted":
                    self.token = body.get("token")
            return
        headers = {"Admission-Token": self.token}
        matches = self.client.get("/matches", headers=headers, name="browse")
        if self.bought or matches.status_code != 200:
            return
        catalog = matches.json()
        if not catalog:
            return
        match_id = catalog[0]["id"]
        reservation_id = None
        with self.client.post(
            f"/matches/{match_id}/ga-reservations",
            json={"session_id": self.visitor_id, "quantity": 1},
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            name="ga-reserve",
            catch_response=True,
        ) as response:
            if response.status_code in {200, 201}:
                reservation_id = response.json()["id"]
                response.success()
            elif response.status_code == 409:
                response.success()
                self.bought = True
                return
            else:
                response.failure(f"ga-reserve {response.status_code}")
                return
        with self.client.post(
            "/checkout",
            json={"session_id": self.visitor_id, "ga_reservation_id": reservation_id},
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            name="checkout",
            catch_response=True,
        ) as response:
            if response.status_code in {200, 201, 402, 409}:
                response.success()
            else:
                response.failure(f"checkout {response.status_code}")
        self.bought = True
