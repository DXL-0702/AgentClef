from uuid import UUID

from server.config import Settings, get_settings
from server.db import create_database_engine, create_session_factory
from server.domain.repository import SqlAlchemyAssetRepository
from server.schemas.assets import TranscriptionJobStatus
from worker.app import celery_app


def mark_transcription_job_status(
    *,
    job_id: UUID,
    status: TranscriptionJobStatus,
    settings: Settings,
) -> dict[str, str]:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.update_transcription_job_status(job_id, status)
    if job is None:
        return {
            "job_id": str(job_id),
            "status": "not_found",
        }
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
    return mark_transcription_status_task(job_id, TranscriptionJobStatus.preprocessing.value)
