import pytest
from fastapi.testclient import TestClient

from arena_onsale.api.app import create_app
from arena_onsale.shared.settings import Settings


@pytest.mark.integration
def test_ready_probe_reports_postgres_redis_and_pool() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.get("/health/ready")
    if response.status_code == 503:
        pytest.skip(str(response.json()))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["postgres"] == "ok"
    assert payload["redis"] == "ok"
    assert "checked_out" in payload["pool"]
