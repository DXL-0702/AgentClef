from celery import Celery

from server.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "agentclef_worker",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["worker.tasks"],
    )
    app.conf.update(task_track_started=True)
    return app


celery_app = create_celery_app()


@celery_app.task(name="agentclef.ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
