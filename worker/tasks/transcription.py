from contextlib import suppress
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

from server.config import Settings, get_settings
from server.db import SessionFactory, create_database_engine, create_session_factory
from server.domain.assets import AudioAsset, TranscriptionJob
from server.domain.repository import SqlAlchemyAssetRepository
from server.schemas.assets import TranscriptionJobStatus, utc_now
from worker.app import celery_app
from worker.pipeline.analysis import analyze_timing
from worker.pipeline.amt import BasicPitchBaselineAdapter
from worker.pipeline.audio import (
    build_normalized_audio_path,
    normalize_audio_to_wav,
    resolve_stored_audio_path,
)
from worker.pipeline.draft import build_draft_score


_session_factories: dict[str, SessionFactory] = {}
_session_factories_lock = Lock()
RUNNABLE_BASELINE_STATUSES = {
    TranscriptionJobStatus.uploaded,
    TranscriptionJobStatus.preprocessing,
    TranscriptionJobStatus.transcribing,
    TranscriptionJobStatus.postprocessing,
    TranscriptionJobStatus.draft_ready,
    TranscriptionJobStatus.preprocessing_failed,
    TranscriptionJobStatus.transcription_failed,
    TranscriptionJobStatus.postprocessing_failed,
}


def get_worker_session_factory(settings: Settings) -> SessionFactory:
    dsn = str(settings.postgres_dsn)
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


def load_transcription_job_context(
    *,
    job_id: UUID,
    settings: Settings,
) -> tuple[TranscriptionJob, AudioAsset]:
    session_factory = get_worker_session_factory(settings)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.get_transcription_job(job_id)
        if job is None:
            raise ValueError(f"TranscriptionJob with ID {job_id} not found")
        audio_asset = repository.get_audio_asset(job.audio_asset_id)
        if audio_asset is None:
            raise ValueError(f"AudioAsset with ID {job.audio_asset_id} not found")
        return job, audio_asset


def create_draft_score_for_job(
    *,
    job: TranscriptionJob,
    payload: dict[str, Any],
    draft_score_id: UUID,
    settings: Settings,
) -> str:
    session_factory = get_worker_session_factory(settings)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        existing_draft_score = repository.get_draft_score_for_job(job.id)
        if existing_draft_score is not None:
            return str(existing_draft_score.id)
        draft_score = repository.create_draft_score(
            draft_score_id=draft_score_id,
            project_id=job.project_id,
            transcription_job_id=job.id,
            version=1,
            payload=payload,
        )
        return str(draft_score.id)


def get_existing_draft_score_id_for_job(*, job_id: UUID, settings: Settings) -> str | None:
    session_factory = get_worker_session_factory(settings)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        draft_score = repository.get_draft_score_for_job(job_id)
        return str(draft_score.id) if draft_score is not None else None


def build_draft_ready_result(*, job_id: UUID, draft_score_id: str) -> dict[str, str]:
    return {
        "job_id": str(job_id),
        "status": TranscriptionJobStatus.draft_ready.value,
        "draft_score_id": draft_score_id,
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
    settings = get_settings()
    parsed_job_id = UUID(job_id)
    job, audio_asset = load_transcription_job_context(job_id=parsed_job_id, settings=settings)
    if job.status == TranscriptionJobStatus.draft_ready:
        draft_score_id = get_existing_draft_score_id_for_job(
            job_id=parsed_job_id, settings=settings
        )
        if draft_score_id is not None:
            return build_draft_ready_result(job_id=parsed_job_id, draft_score_id=draft_score_id)
    if job.status not in RUNNABLE_BASELINE_STATUSES:
        raise ValueError(f"cannot run baseline transcription in status: {job.status.value}")
    existing_draft_score_id = get_existing_draft_score_id_for_job(
        job_id=parsed_job_id,
        settings=settings,
    )
    if existing_draft_score_id is not None:
        mark_transcription_job_status(
            job_id=parsed_job_id,
            status=TranscriptionJobStatus.draft_ready,
            settings=settings,
        )
        return build_draft_ready_result(
            job_id=parsed_job_id,
            draft_score_id=existing_draft_score_id,
        )

    mark_transcription_job_status(
        job_id=parsed_job_id,
        status=TranscriptionJobStatus.preprocessing,
        settings=settings,
    )

    try:
        storage_root = Path(settings.file_storage_path)
        source_audio_path = resolve_stored_audio_path(
            storage_root=storage_root,
            project_id=audio_asset.project_id,
            stored_filename=audio_asset.stored_filename,
        )
        normalized_audio_path = build_normalized_audio_path(
            storage_root=storage_root,
            project_id=audio_asset.project_id,
            job_id=job.id,
        )
        normalized_audio = normalize_audio_to_wav(
            source_path=source_audio_path,
            destination_path=normalized_audio_path,
        )
    except Exception:
        _mark_failed_job_status(
            job_id=parsed_job_id,
            status=TranscriptionJobStatus.preprocessing_failed,
            settings=settings,
        )
        raise

    mark_transcription_job_status(
        job_id=parsed_job_id,
        status=TranscriptionJobStatus.transcribing,
        settings=settings,
    )
    try:
        analysis = analyze_timing(normalized_audio)
        note_candidates = BasicPitchBaselineAdapter().transcribe(normalized_audio, analysis)
    except Exception:
        _mark_failed_job_status(
            job_id=parsed_job_id,
            status=TranscriptionJobStatus.transcription_failed,
            settings=settings,
        )
        raise

    mark_transcription_job_status(
        job_id=parsed_job_id,
        status=TranscriptionJobStatus.postprocessing,
        settings=settings,
    )
    try:
        draft_score = build_draft_score(
            project_id=audio_asset.project_id,
            analysis=analysis,
            note_candidates=note_candidates,
            created_at=utc_now(),
        )
        draft_score_id = create_draft_score_for_job(
            job=job,
            payload=draft_score.model_dump(mode="json"),
            draft_score_id=draft_score.id,
            settings=settings,
        )
    except Exception:
        _mark_failed_job_status(
            job_id=parsed_job_id,
            status=TranscriptionJobStatus.postprocessing_failed,
            settings=settings,
        )
        raise

    mark_transcription_job_status(
        job_id=parsed_job_id,
        status=TranscriptionJobStatus.draft_ready,
        settings=settings,
    )
    return build_draft_ready_result(job_id=parsed_job_id, draft_score_id=draft_score_id)


def _mark_failed_job_status(
    *,
    job_id: UUID,
    status: TranscriptionJobStatus,
    settings: Settings,
) -> None:
    with suppress(Exception):
        mark_transcription_job_status(job_id=job_id, status=status, settings=settings)
