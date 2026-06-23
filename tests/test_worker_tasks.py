import io
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest
from pytest import MonkeyPatch

from server.config import Settings
from server.db import create_database_engine, create_database_schema, create_session_factory
from server.domain.repository import SqlAlchemyAssetRepository
from server.models import DraftScoreRecord
from server.schemas.assets import ProjectCreateRequest, TranscriptionJobStatus
from shared.schemas.score import DraftScore
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
            duration_seconds=0.25,
        )
        return str(job.id)


def create_transcription_job_with_audio(settings: Settings) -> str:
    engine = create_database_engine(settings)
    create_database_schema(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        project = repository.create_project(ProjectCreateRequest(title="Worker pipeline"))
        audio_asset, job = repository.create_audio_asset_with_job(
            project_id=project.id,
            original_filename="demo.wav",
            stored_filename="worker-demo.wav",
            content_type="audio/wav",
            extension=".wav",
            size_bytes=128,
            duration_seconds=0.25,
        )

    audio_dir = Path(settings.file_storage_path) / "projects" / str(project.id) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / audio_asset.stored_filename).write_bytes(build_wav_bytes())
    return str(job.id)


def build_wav_bytes(*, duration_seconds: float = 0.25, sample_rate: int = 8_000) -> bytes:
    frame_count = int(duration_seconds * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


def get_job_status(settings: Settings, job_id: str) -> TranscriptionJobStatus:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.get_transcription_job(UUID(job_id))
        assert job is not None
        return job.status


def get_draft_score_payload(settings: Settings, job_id: str) -> dict[str, object]:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        draft_score = repository.get_draft_score_for_job(UUID(job_id))
        assert draft_score is not None
        return draft_score.payload


def count_draft_scores_for_job(settings: Settings, job_id: str) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        return (
            session.query(DraftScoreRecord)
            .filter(DraftScoreRecord.transcription_job_id == UUID(job_id))
            .count()
        )


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


def test_mark_transcription_job_status_raises_for_missing_job(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-missing.db"),
    )
    engine = create_database_engine(settings)
    create_database_schema(engine)
    missing_job_id = UUID("00000000-0000-0000-0000-000000000000")

    with pytest.raises(ValueError, match=f"TranscriptionJob with ID {missing_job_id} not found"):
        mark_transcription_job_status(
            job_id=missing_job_id,
            status=TranscriptionJobStatus.preprocessing,
            settings=settings,
        )


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


def test_worker_session_factory_initializes_once_under_threads(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-thread-cache.db"),
    )
    created_engines = []
    real_create_database_engine = create_database_engine

    def counted_create_database_engine(settings: Settings) -> object:
        engine = real_create_database_engine(settings)
        created_engines.append(engine)
        return engine

    monkeypatch.setattr(
        "worker.tasks.transcription.create_database_engine",
        counted_create_database_engine,
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        session_factories = list(
            executor.map(lambda _: get_worker_session_factory(settings), range(16))
        )

    assert len(created_engines) == 1
    assert all(session_factory is session_factories[0] for session_factory in session_factories)


def test_run_transcription_baseline_task_creates_valid_draft_score(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-baseline.db"),
        file_storage_path=str(tmp_path / "storage"),
    )
    job_id = create_transcription_job_with_audio(settings)

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        result = run_transcription_baseline_task(job_id)

    assert result["job_id"] == job_id
    assert result["status"] == TranscriptionJobStatus.draft_ready.value
    assert UUID(result["draft_score_id"])
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.draft_ready

    draft_score_payload = get_draft_score_payload(settings, job_id)
    draft_score = DraftScore.model_validate(draft_score_payload)
    assert str(draft_score.id) == result["draft_score_id"]
    assert draft_score.notes
    assert draft_score.notes[0].track_id == "track-main"
    assert draft_score.uncertainty_markers
    assert list((tmp_path / "storage").rglob("normalized.wav"))


def test_run_transcription_baseline_task_returns_existing_ready_draft(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-existing-draft.db"),
        file_storage_path=str(tmp_path / "storage"),
    )
    job_id = create_transcription_job_with_audio(settings)

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        first_result = run_transcription_baseline_task(job_id)
        second_result = run_transcription_baseline_task(job_id)

    assert first_result == second_result
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.draft_ready
    assert count_draft_scores_for_job(settings, job_id) == 1


def test_run_transcription_baseline_task_reuses_existing_draft_after_failed_retry(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-failed-retry.db"),
        file_storage_path=str(tmp_path / "storage"),
    )
    job_id = create_transcription_job_with_audio(settings)

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        first_result = run_transcription_baseline_task(job_id)
        mark_transcription_job_status(
            job_id=UUID(job_id),
            status=TranscriptionJobStatus.postprocessing_failed,
            settings=settings,
        )
        retry_result = run_transcription_baseline_task(job_id)

    assert retry_result == first_result
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.draft_ready
    assert count_draft_scores_for_job(settings, job_id) == 1


@pytest.mark.parametrize(
    "recoverable_status",
    [TranscriptionJobStatus.transcribing, TranscriptionJobStatus.postprocessing],
)
def test_run_transcription_baseline_task_recovers_active_status(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    recoverable_status: TranscriptionJobStatus,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / f"worker-active-{recoverable_status.value}.db"),
        file_storage_path=str(tmp_path / "storage"),
    )
    job_id = create_transcription_job_with_audio(settings)
    mark_transcription_job_status(
        job_id=UUID(job_id),
        status=recoverable_status,
        settings=settings,
    )

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        result = run_transcription_baseline_task(job_id)

    assert result["status"] == TranscriptionJobStatus.draft_ready.value
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.draft_ready
    assert count_draft_scores_for_job(settings, job_id) == 1


def test_run_transcription_baseline_task_regenerates_missing_ready_draft(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-ready-missing-draft.db"),
        file_storage_path=str(tmp_path / "storage"),
    )
    job_id = create_transcription_job_with_audio(settings)
    mark_transcription_job_status(
        job_id=UUID(job_id),
        status=TranscriptionJobStatus.draft_ready,
        settings=settings,
    )

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        result = run_transcription_baseline_task(job_id)

    assert result["status"] == TranscriptionJobStatus.draft_ready.value
    assert get_job_status(settings, job_id) == TranscriptionJobStatus.draft_ready
    assert count_draft_scores_for_job(settings, job_id) == 1
    DraftScore.model_validate(get_draft_score_payload(settings, job_id))


def test_run_transcription_baseline_task_marks_preprocessing_failed_when_audio_missing(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    clear_worker_session_factory_cache()
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "worker-missing-audio.db"),
        file_storage_path=str(tmp_path / "storage"),
    )
    job_id = create_transcription_job(settings)

    with monkeypatch.context() as patched:
        patched.setattr("worker.tasks.transcription.get_settings", lambda: settings)
        with pytest.raises(RuntimeError, match="stored audio file not found"):
            run_transcription_baseline_task(job_id)

    assert get_job_status(settings, job_id) == TranscriptionJobStatus.preprocessing_failed
