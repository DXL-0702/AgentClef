import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from server.config import Settings


def isolated_settings(monkeypatch: MonkeyPatch, **overrides: object) -> Settings:
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    return Settings(**overrides)  # type: ignore[arg-type]


def test_settings_defaults_are_valid(monkeypatch: MonkeyPatch) -> None:
    settings = isolated_settings(monkeypatch)

    assert settings.app_name == "AgentClef"
    assert settings.api_port == 8000
    assert settings.environment == "development"
    assert settings.upload_max_mb > 0
    assert settings.upload_max_seconds > 0
    assert settings.llm_provider == "disabled"
    assert settings.llm_api_key is None


@pytest.mark.parametrize("field_name", ["postgres_dsn", "redis_url", "file_storage_path"])
def test_settings_reject_empty_required_strings(monkeypatch: MonkeyPatch, field_name: str) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        isolated_settings(monkeypatch, **{field_name: "   "})


def test_settings_reject_invalid_environment(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="environment must be one of"):
        isolated_settings(monkeypatch, environment="local")


def test_settings_reject_invalid_upload_limits(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        isolated_settings(monkeypatch, upload_max_mb=0)

    with pytest.raises(ValidationError):
        isolated_settings(monkeypatch, upload_max_seconds=-1)


def test_settings_reject_wildcard_cors_with_credentials(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="cors_origins must not contain"):
        isolated_settings(monkeypatch, cors_origins=["http://localhost:5173", "*"])


def test_settings_require_api_key_when_llm_provider_is_enabled(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="llm_api_key must be provided"):
        isolated_settings(monkeypatch, llm_provider="openai", llm_api_key=" ")
