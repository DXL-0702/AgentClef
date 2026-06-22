from celery import Celery

from server.config import Settings, get_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    runtime_settings = settings or get_settings()
    app = Celery(
        "agentclef_worker",
        broker=runtime_settings.redis_url,
        backend=runtime_settings.redis_url,
        include=["worker.tasks", "worker.tasks.transcription"],
    )
    app.conf.update(
        task_track_started=True,
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = create_celery_app()


@celery_app.task(name="agentclef.ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
