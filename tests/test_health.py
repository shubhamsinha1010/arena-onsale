from fastapi.testclient import TestClient

from arena_onsale.api.app import create_app
from arena_onsale.shared.settings import Settings


def test_live_probe_does_not_need_postgres_or_redis() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_exposes_pool_gauges() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "arena_db_pool_size" in body
    assert "arena_db_pool_checked_out" in body
