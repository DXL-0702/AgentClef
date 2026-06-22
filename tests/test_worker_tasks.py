from pathlib import Path
from uuid import UUID

from pytest import MonkeyPatch

from server.config import Settings
from server.db import create_database_engine, create_database_schema, create_session_factory
from server.domain.repository import SqlAlchemyAssetRepository
from server.schemas.assets import ProjectCreateRequest, TranscriptionJobStatus
from tests.settings_helpers import make_settings
from worker.app import create_celery_app
from worker.tasks.transcription import (
    clear_worker_session_factory_cache,
    get_worker_session_factory,
    mark_transcription_job_status,
    mark_transcription_status_task,
    run_transcription_baseline_task,
)


def sqlite_file_dsn(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def create_transcription_job(settings: Settings) -> str:
    engine = create_database_engine(settings)
    create_database_schema(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        project = repository.create_project(ProjectCreateRequest(title="Worker baseline"))
        _, job = repository.create_audio_asset_with_job(
            project_id=project.id,
            original_filename="demo.wav",
            stored_filename="worker-demo.wav",
            content_type="audio/wav",
            extension=".wav",
            size_bytes=128,
        )
        return str(job.id)


def get_job_status(settings: Settings, job_id: str) -> TranscriptionJobStatus:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.get_transcription_job(UUID(job_id))
        assert job is not None
        return job.status


def test_mark_transcription_job_status_updates_persisted_job(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker.db"),
    )
    job_id = create_transcription_job(settings)

    result = mark_transcription_job_status(
        job_id=UUID(job_id),
        status=TranscriptionJobStatus.preprocessing,
        settings=settings,
    )

    assert result == {"job_id": job_id, "status": "preprocessing"}
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.preprocessing


def test_mark_transcription_status_task_runs_in_eager_mode(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-eager.db"),
    )
    job_id = create_transcription_job(settings)
    celery_app = create_celery_app(settings)
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_store_eager_result = True

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        result = mark_transcription_status_task.apply(
            args=[job_id, TranscriptionJobStatus.preprocessing.value],
            app=celery_app,
        )

    assert result.successful()
    assert result.result == {"job_id": job_id, "status": "preprocessing"}
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.preprocessing


def test_worker_session_factory_is_cached_by_dsn(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-cache.db"),
    )

    first_session_factory = get_worker_session_factory(settings)
    second_session_factory = get_worker_session_factory(settings)

    assert second_session_factory is first_session_factory


def test_run_transcription_baseline_task_marks_job_preprocessing(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-baseline.db"),
    )
    job_id = create_transcription_job(settings)

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        result = run_transcription_baseline_task(job_id)

    assert result == {"job_id": job_id, "status": "preprocessing"}
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.preprocessing
