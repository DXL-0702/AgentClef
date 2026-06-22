from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from server.app import create_app
from tests.settings_helpers import make_settings


def test_health_check_returns_public_runtime_state(monkeypatch: MonkeyPatch) -> None:
    settings = make_settings(monkeypatch)
    app = create_app(settings)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "AgentClef"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "development"
    assert payload["postgres_configured"] is True
    assert payload["redis_configured"] is True
    assert payload["file_storage_configured"] is True
    assert payload["upload_limits"] == {"max_mb": 50, "max_seconds": 300}
    assert payload["llm_provider"] == "disabled"
    assert "file_storage_path" not in payload
    assert "llm_api_key" not in payload
