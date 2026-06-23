import asyncio
import json
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from server.app import create_app
from server.api import jobs as jobs_api
from server.domain.assets import Project, TranscriptionJob
from server.domain.repository import SqlAlchemyAssetRepository
from server.schemas.assets import ProjectCreateRequest, TranscriptionJobStatus, utc_now
from shared.schemas.score import DraftScore
from tests.settings_helpers import make_settings
from worker.pipeline.analysis import TimingAnalysis
from worker.pipeline.amt import NoteCandidate
from worker.pipeline.draft import build_draft_score


def create_test_app(monkeypatch: MonkeyPatch, tmp_path: Path) -> FastAPI:
    settings = make_settings(
        monkeypatch,
        postgres_dsn="sqlite+pysqlite:///:memory:",
        file_storage_path=str(tmp_path / "storage"),
    )
    return create_app(settings, initialize_database=True)


def create_project_with_job(app: FastAPI) -> tuple[Project, TranscriptionJob]:
    session_factory = app.state.session_factory
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        project = repository.create_project(ProjectCreateRequest(title="API project"))
        _, job = repository.create_audio_asset_with_job(
            project_id=project.id,
            original_filename="demo.wav",
            stored_filename="api-demo.wav",
            content_type="audio/wav",
            extension=".wav",
            size_bytes=128,
            duration_seconds=0.25,
        )
        return project, job


def create_draft_score(app: FastAPI, project: Project, job: TranscriptionJob) -> DraftScore:
    analysis = TimingAnalysis(
        duration_seconds=1.0,
        tempo_bpm=120.0,
        seconds_per_beat=0.5,
        meter_numerator=4,
        meter_denominator=4,
    )
    draft_score = build_draft_score(
        project_id=project.id,
        analysis=analysis,
        note_candidates=[
            NoteCandidate(
                midi=60,
                name="C4",
                start_seconds=0.0,
                end_seconds=0.45,
                confidence=0.35,
            ),
        ],
        created_at=utc_now(),
    )
    session_factory = app.state.session_factory
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        repository.create_draft_score(
            draft_score_id=draft_score.id,
            project_id=project.id,
            transcription_job_id=job.id,
            version=draft_score.version,
            payload=draft_score.model_dump(mode="json"),
        )
    return draft_score


def update_job_status(
    app: FastAPI,
    job: TranscriptionJob,
    status: TranscriptionJobStatus,
) -> None:
    session_factory = app.state.session_factory
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        updated_job = repository.update_transcription_job_status(job.id, status)
        assert updated_job is not None


def assert_error_detail(response_payload: dict[str, object], *, code: str, message: str) -> None:
    assert response_payload["detail"] == {
        "code": code,
        "message": message,
    }


def test_get_project_returns_project_metadata(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    project, _ = create_project_with_job(app)
    client = TestClient(app)

    response = client.get(f"/projects/{project.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(project.id)
    assert response.json()["title"] == "API project"


def test_get_project_returns_not_found_for_missing_project(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/projects/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert_error_detail(response.json(), code="project_not_found", message="project not found")


def test_get_job_returns_transcription_job_state(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    _, job = create_project_with_job(app)
    client = TestClient(app)

    response = client.get(f"/jobs/{job.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(job.id)
    assert response.json()["status"] == TranscriptionJobStatus.uploaded.value


def test_get_job_returns_not_found_for_missing_job(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/jobs/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert_error_detail(response.json(), code="job_not_found", message="job not found")


def test_get_project_draft_returns_valid_draft_score(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    project, job = create_project_with_job(app)
    draft_score = create_draft_score(app, project, job)
    client = TestClient(app)

    response = client.get(f"/projects/{project.id}/draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(draft_score.id)
    assert payload["project_id"] == str(project.id)
    assert DraftScore.model_validate(payload).id == draft_score.id


def test_api_prefixed_project_job_and_draft_routes(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    project, job = create_project_with_job(app)
    draft_score = create_draft_score(app, project, job)
    client = TestClient(app)

    project_response = client.get(f"/api/projects/{project.id}")
    job_response = client.get(f"/api/jobs/{job.id}")
    draft_response = client.get(f"/api/projects/{project.id}/draft")

    assert project_response.status_code == 200
    assert project_response.json()["id"] == str(project.id)
    assert job_response.status_code == 200
    assert job_response.json()["id"] == str(job.id)
    assert draft_response.status_code == 200
    assert draft_response.json()["id"] == str(draft_score.id)


def test_openapi_schema_exposes_api_prefixed_business_routes_only(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/projects/{project_id}" in paths
    assert "/api/jobs/{job_id}" in paths
    assert "/api/jobs/{job_id}/events" in paths
    assert "/api/projects/{project_id}/draft" in paths
    assert "/projects/{project_id}" not in paths
    assert "/jobs/{job_id}" not in paths
    assert "/jobs/{job_id}/events" not in paths


def test_get_project_draft_returns_not_found_before_draft_ready(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    project, _ = create_project_with_job(app)
    client = TestClient(app)

    response = client.get(f"/projects/{project.id}/draft")

    assert response.status_code == 404
    assert_error_detail(
        response.json(),
        code="draft_score_not_found",
        message="draft score not found",
    )


def test_job_events_streams_current_status(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    _, job = create_project_with_job(app)
    client = TestClient(app)

    response = client.get(f"/jobs/{job.id}/events?max_events=1&poll_interval_seconds=0.1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: job_status" in response.text
    event_payload = _parse_first_sse_data(response.text)
    assert event_payload["id"] == str(job.id)
    assert event_payload["status"] == TranscriptionJobStatus.uploaded.value


def test_job_events_stop_after_terminal_status(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    _, job = create_project_with_job(app)
    update_job_status(app, job, TranscriptionJobStatus.draft_ready)
    client = TestClient(app)

    response = client.get(f"/api/jobs/{job.id}/events?poll_interval_seconds=0.1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: job_status") == 1
    event_payload = _parse_first_sse_data(response.text)
    assert event_payload["id"] == str(job.id)
    assert event_payload["status"] == TranscriptionJobStatus.draft_ready.value


def test_job_event_iterator_loads_job_state_in_thread(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    _, job = create_project_with_job(app)
    to_thread_calls: list[str] = []

    async def fake_to_thread(
        func: Callable[..., object],
        /,
        *args: object,
        **kwargs: object,
    ) -> object:
        to_thread_calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(jobs_api.asyncio, "to_thread", fake_to_thread)

    async def collect_first_event() -> str:
        event_stream = jobs_api._iter_job_status_events(
            session_factory=app.state.session_factory,
            job_id=job.id,
            poll_interval_seconds=0.1,
            max_events=1,
        )
        return await anext(event_stream)

    event = asyncio.run(collect_first_event())

    assert to_thread_calls == ["_load_job_response_from_session_factory"]
    assert "event: job_status" in event
    event_payload = _parse_first_sse_data(event)
    assert event_payload["id"] == str(job.id)


def test_job_events_returns_not_found_for_missing_job(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/jobs/00000000-0000-0000-0000-000000000000/events")

    assert response.status_code == 404
    assert_error_detail(response.json(), code="job_not_found", message="job not found")


def _parse_first_sse_data(payload: str) -> dict[str, object]:
    for line in payload.splitlines():
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    raise AssertionError("SSE payload did not include a data line")
