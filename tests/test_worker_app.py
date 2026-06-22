from pytest import MonkeyPatch

from tests.settings_helpers import make_settings
from worker.app import create_celery_app


def test_create_celery_app_uses_injected_settings(monkeypatch: MonkeyPatch) -> None:
    settings = make_settings(
        monkeypatch=monkeypatch,
        redis_url="redis://localhost:6380/2",
    )

    app = create_celery_app(settings)

    assert app.conf.broker_url == "redis://localhost:6380/2"
    assert app.conf.result_backend == "redis://localhost:6380/2"


def test_create_celery_app_includes_task_modules(monkeypatch: MonkeyPatch) -> None:
    settings = make_settings(monkeypatch)

    app = create_celery_app(settings)

    assert "worker.tasks" in app.conf.include
