import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from tests.settings_helpers import clear_agentclef_env, make_settings, make_settings_from_env


def test_settings_defaults_are_valid(monkeypatch: MonkeyPatch) -> None:
    settings = make_settings(monkeypatch)

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
        make_settings(monkeypatch, **{field_name: "   "})


def test_settings_reject_invalid_environment(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="environment must be one of"):
        make_settings(monkeypatch, environment="local")


def test_settings_reject_invalid_upload_limits(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        make_settings(monkeypatch, upload_max_mb=0)

    with pytest.raises(ValidationError):
        make_settings(monkeypatch, upload_max_seconds=-1)


def test_settings_reject_wildcard_cors_with_credentials(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="cors_origins must not contain"):
        make_settings(monkeypatch, cors_origins=["http://localhost:5173", "*"])


def test_settings_parse_cors_origins_from_json_env(monkeypatch: MonkeyPatch) -> None:
    clear_agentclef_env(monkeypatch)
    monkeypatch.setenv("AGENTCLEF_CORS_ORIGINS", '["http://localhost:5173","http://127.0.0.1:5173"]')

    settings = make_settings_from_env()

    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_settings_parse_quoted_json_cors_origins(monkeypatch: MonkeyPatch) -> None:
    clear_agentclef_env(monkeypatch)
    monkeypatch.setenv(
        "AGENTCLEF_CORS_ORIGINS",
        '\'["http://localhost:5173","http://127.0.0.1:5173"]\'',
    )

    settings = make_settings_from_env()

    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_settings_parse_cors_origins_from_comma_separated_env(monkeypatch: MonkeyPatch) -> None:
    clear_agentclef_env(monkeypatch)
    monkeypatch.setenv("AGENTCLEF_CORS_ORIGINS", "http://localhost:5173, http://127.0.0.1:5173")

    settings = make_settings_from_env()

    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_settings_parse_quoted_comma_separated_cors_origins(monkeypatch: MonkeyPatch) -> None:
    clear_agentclef_env(monkeypatch)
    monkeypatch.setenv(
        "AGENTCLEF_CORS_ORIGINS",
        '"http://localhost:5173, http://127.0.0.1:5173"',
    )

    settings = make_settings_from_env()

    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_settings_parse_individually_quoted_cors_origins(monkeypatch: MonkeyPatch) -> None:
    clear_agentclef_env(monkeypatch)
    monkeypatch.setenv(
        "AGENTCLEF_CORS_ORIGINS",
        '"http://localhost:5173", \'http://127.0.0.1:5173\'',
    )

    settings = make_settings_from_env()

    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_settings_require_api_key_when_llm_provider_is_enabled(monkeypatch: MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="llm_api_key must be provided"):
        make_settings(monkeypatch, llm_provider="openai", llm_api_key=" ")
