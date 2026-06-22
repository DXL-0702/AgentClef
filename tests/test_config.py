from server.config import Settings


def test_settings_defaults_are_valid() -> None:
    settings = Settings()

    assert settings.app_name == "AgentClef"
    assert settings.api_port == 8000
    assert settings.environment == "development"
    assert settings.upload_max_mb > 0
    assert settings.upload_max_seconds > 0
