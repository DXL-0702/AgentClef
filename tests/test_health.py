from fastapi.testclient import TestClient

from server.main import app


def test_health_check_returns_public_runtime_state() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "AgentClef"
    assert payload["postgres_configured"] is True
    assert payload["redis_configured"] is True
    assert payload["file_storage_configured"] is True
    assert "file_storage_path" not in payload
    assert "llm_api_key" not in payload
