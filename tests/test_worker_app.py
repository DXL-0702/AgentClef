from pytest import MonkeyPatch

from server.config import Settings
from worker.app import create_celery_app


def isolated_settings(monkeypatch: MonkeyPatch, **overrides: object) -> Settings:
    for field_name in Settings.model_fields:
        monkeypatch.delenv(f"AGENTCLEF_{field_name.upper()}", raising=False)
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    return Settings(**overrides)  # type: ignore[arg-type]


def test_create_celery_app_uses_injected_settings(monkeypatch: MonkeyPatch) -> None:
    settings = isolated_settings(
        monkeypatch=monkeypatch,
        redis_url="redis://localhost:6380/2",
    )

    app = create_celery_app(settings)

    assert app.conf.broker_url == "redis://localhost:6380/2"
    assert app.conf.result_backend == "redis://localhost:6380/2"


def test_create_celery_app_includes_task_modules(monkeypatch: MonkeyPatch) -> None:
    settings = isolated_settings(monkeypatch)

    app = create_celery_app(settings)

    assert "worker.tasks" in app.conf.include
