"""Locust personas for admitted vs queued fans.

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
    """The small cohort that made it through the bulkhead — browse only here."""

    wait_time = between(0.5, 2.0)
    weight = 1

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
        self.client.get(
            "/matches",
            headers={"Admission-Token": self.token},
            name="browse",
        )
