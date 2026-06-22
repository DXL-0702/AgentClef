from threading import Lock
from uuid import UUID

from server.config import Settings, get_settings
from server.db import SessionFactory, create_database_engine, create_session_factory
from server.domain.repository import SqlAlchemyAssetRepository
from server.schemas.assets import TranscriptionJobStatus
from worker.app import celery_app


_session_factories: dict[str, SessionFactory] = {}
_session_factories_lock = Lock()


def get_worker_session_factory(settings: Settings) -> SessionFactory:
    dsn = settings.postgres_dsn
    if dsn not in _session_factories:
        with _session_factories_lock:
            if dsn not in _session_factories:
                engine = create_database_engine(settings)
                _session_factories[dsn] = create_session_factory(engine)
    return _session_factories[dsn]


def clear_worker_session_factory_cache() -> None:
    with _session_factories_lock:
        _session_factories.clear()


def mark_transcription_job_status(
    *,
    job_id: UUID,
    status: TranscriptionJobStatus,
    settings: Settings,
) -> dict[str, str]:
    session_factory = get_worker_session_factory(settings)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.update_transcription_job_status(job_id, status)
    if job is None:
        raise ValueError(f"TranscriptionJob with ID {job_id} not found")
    return {
        "job_id": str(job.id),
        "status": job.status.value,
    }


@celery_app.task(name="agentclef.transcription.mark_status")
def mark_transcription_status_task(job_id: str, status: str) -> dict[str, str]:
    return mark_transcription_job_status(
        job_id=UUID(job_id),
        status=TranscriptionJobStatus(status),
        settings=get_settings(),
    )


@celery_app.task(name="agentclef.transcription.run_baseline")
def run_transcription_baseline_task(job_id: str) -> dict[str, str]:
    return mark_transcription_job_status(
        job_id=UUID(job_id),
        status=TranscriptionJobStatus.preprocessing,
        settings=get_settings(),
    )
