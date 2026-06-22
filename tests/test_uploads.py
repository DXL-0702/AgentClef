import asyncio
import io
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi import UploadFile
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from starlette.datastructures import Headers

from server.app import create_app
from server.domain.assets import AudioAsset, Project, TranscriptionJob
from server.domain.repository import SqlAlchemyAssetRepository, get_asset_repository
from server.domain.storage import UploadValidationError, store_audio_upload
from server.schemas.assets import AudioAssetStatus, ProjectCreateRequest, TranscriptionJobStatus, utc_now
from tests.settings_helpers import make_settings


class FakeCeleryApp:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.fail_on_send = fail_on_send
        self.sent_tasks: list[tuple[str, list[str]]] = []

    def send_task(self, name: str, args: list[str]) -> None:
        if self.fail_on_send:
            raise RuntimeError("simulated worker dispatch failure")
        self.sent_tasks.append((name, args))


class FailingTranscriptionJobRepository:
    def __init__(self) -> None:
        self._projects: dict[UUID, Project] = {}
        self.created_audio_asset: AudioAsset | None = None

    def create_project(self, payload: ProjectCreateRequest) -> Project:
        project = Project(
            id=uuid4(),
            title=payload.title,
            created_at=utc_now(),
        )
        self._projects[project.id] = project
        return project

    def get_project(self, project_id: UUID) -> Project | None:
        return self._projects.get(project_id)

    def create_audio_asset_with_job(
        self,
        *,
        project_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
    ) -> tuple[AudioAsset, TranscriptionJob]:
        self.created_audio_asset = AudioAsset(
            id=uuid4(),
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            extension=extension,
            size_bytes=size_bytes,
            status=AudioAssetStatus.uploaded,
            created_at=utc_now(),
        )
        raise RuntimeError("simulated task creation failure")


def create_test_client(monkeypatch: MonkeyPatch, storage_path: Path, upload_max_mb: int = 1) -> TestClient:
    settings = make_settings(
        monkeypatch,
        postgres_dsn="sqlite+pysqlite:///:memory:",
        file_storage_path=str(storage_path),
        upload_max_mb=upload_max_mb,
    )
    return TestClient(create_app(settings, initialize_database=True))


def create_test_app(monkeypatch: MonkeyPatch, storage_path: Path) -> FastAPI:
    settings = make_settings(
        monkeypatch,
        postgres_dsn="sqlite+pysqlite:///:memory:",
        file_storage_path=str(storage_path),
    )
    return create_app(settings, initialize_database=True)


def update_job_status(app: FastAPI, job_id: str, status: TranscriptionJobStatus) -> None:
    session_factory = app.state.session_factory
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.update_transcription_job_status(UUID(job_id), status)
        assert job is not None


def get_job_status(app: FastAPI, job_id: str) -> TranscriptionJobStatus:
    session_factory = app.state.session_factory
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.get_transcription_job(UUID(job_id))
        assert job is not None
        return job.status


def create_project(client: TestClient) -> dict[str, str]:
    response = client.post("/projects", json={"title": "Phase 2 upload"})
    assert response.status_code == 201
    return response.json()


def test_create_project_returns_public_project_state(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)

    payload = create_project(client)

    assert payload["title"] == "Phase 2 upload"
    assert "id" in payload
    assert "created_at" in payload


def test_create_project_rejects_blank_title(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)

    response = client.post("/projects", json={"title": "   "})

    assert response.status_code == 422


def test_upload_audio_creates_asset_and_task(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)
    project = create_project(client)

    response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("../unsafe/demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["project"]["id"] == project["id"]
    assert payload["audio_asset"]["original_filename"] == "demo.wav"
    assert payload["audio_asset"]["extension"] == ".wav"
    assert payload["audio_asset"]["content_type"] == "audio/wav"
    assert payload["audio_asset"]["size_bytes"] == len(b"RIFFdemo-audio")
    assert payload["audio_asset"]["status"] == "uploaded"
    assert payload["transcription_job"]["status"] == "uploaded"
    assert payload["transcription_job"]["audio_asset_id"] == payload["audio_asset"]["id"]
    assert "stored_filename" not in payload["audio_asset"]
    assert "storage" not in payload["audio_asset"]

    stored_files = list(tmp_path.rglob("*.wav"))
    assert len(stored_files) == 1
    assert stored_files[0].name != "demo.wav"

    task_response = client.get(f"/tasks/{payload['transcription_job']['id']}")
    assert task_response.status_code == 200
    assert task_response.json() == payload["transcription_job"]


def test_dispatch_transcription_job_sends_worker_task(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    fake_celery_app = FakeCeleryApp()
    app.state.celery_app = fake_celery_app
    client = TestClient(app)
    project = create_project(client)
    upload_response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )
    job = upload_response.json()["transcription_job"]

    response = client.post(f"/tasks/{job['id']}/dispatch")

    assert response.status_code == 202
    payload = response.json()
    assert payload == {
        **job,
        "status": TranscriptionJobStatus.preprocessing.value,
        "updated_at": payload["updated_at"],
    }
    assert get_job_status(app, job["id"]) == TranscriptionJobStatus.preprocessing
    assert fake_celery_app.sent_tasks == [
        ("agentclef.transcription.run_baseline", [job["id"]]),
    ]


def test_dispatch_transcription_job_rejects_duplicate_after_status_update(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    fake_celery_app = FakeCeleryApp()
    app.state.celery_app = fake_celery_app
    client = TestClient(app)
    project = create_project(client)
    upload_response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )
    job = upload_response.json()["transcription_job"]

    first_response = client.post(f"/tasks/{job['id']}/dispatch")
    second_response = client.post(f"/tasks/{job['id']}/dispatch")

    assert first_response.status_code == 202
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "cannot dispatch task in status: preprocessing"
    assert fake_celery_app.sent_tasks == [
        ("agentclef.transcription.run_baseline", [job["id"]]),
    ]


def test_dispatch_transcription_job_rejects_active_task(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    fake_celery_app = FakeCeleryApp()
    app.state.celery_app = fake_celery_app
    client = TestClient(app)
    project = create_project(client)
    upload_response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )
    job = upload_response.json()["transcription_job"]
    update_job_status(app, job["id"], TranscriptionJobStatus.preprocessing)

    response = client.post(f"/tasks/{job['id']}/dispatch")

    assert response.status_code == 400
    assert response.json()["detail"] == "cannot dispatch task in status: preprocessing"
    assert fake_celery_app.sent_tasks == []


def test_dispatch_transcription_job_allows_failed_task_retry(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    fake_celery_app = FakeCeleryApp()
    app.state.celery_app = fake_celery_app
    client = TestClient(app)
    project = create_project(client)
    upload_response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )
    job = upload_response.json()["transcription_job"]
    update_job_status(app, job["id"], TranscriptionJobStatus.transcription_failed)

    response = client.post(f"/tasks/{job['id']}/dispatch")

    assert response.status_code == 202
    payload = response.json()
    assert payload["id"] == job["id"]
    assert payload["status"] == TranscriptionJobStatus.preprocessing.value
    assert get_job_status(app, job["id"]) == TranscriptionJobStatus.preprocessing
    assert fake_celery_app.sent_tasks == [
        ("agentclef.transcription.run_baseline", [job["id"]]),
    ]


def test_dispatch_transcription_job_rolls_back_status_when_worker_dispatch_fails(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = create_test_app(monkeypatch, tmp_path)
    fake_celery_app = FakeCeleryApp(fail_on_send=True)
    app.state.celery_app = fake_celery_app
    client = TestClient(app)
    project = create_project(client)
    upload_response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )
    job = upload_response.json()["transcription_job"]
    update_job_status(app, job["id"], TranscriptionJobStatus.transcription_failed)

    with pytest.raises(RuntimeError, match="simulated worker dispatch failure"):
        client.post(f"/tasks/{job['id']}/dispatch")

    assert get_job_status(app, job["id"]) == TranscriptionJobStatus.transcription_failed
    assert fake_celery_app.sent_tasks == []


def test_upload_audio_normalizes_windows_style_filename(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)
    project = create_project(client)

    response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": (r"..\unsafe\demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )

    assert response.status_code == 201
    assert response.json()["audio_asset"]["original_filename"] == "demo.wav"


def test_upload_audio_removes_file_when_task_creation_fails(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = make_settings(
        monkeypatch,
        postgres_dsn="sqlite+pysqlite:///:memory:",
        file_storage_path=str(tmp_path),
    )
    app = create_app(settings, initialize_database=True)
    repository = FailingTranscriptionJobRepository()
    app.dependency_overrides[get_asset_repository] = lambda: repository
    client = TestClient(app)
    project = create_project(client)

    with pytest.raises(RuntimeError, match="simulated task creation failure"):
        client.post(
            f"/projects/{project['id']}/audio",
            files={"file": ("demo.wav", b"RIFFdemo-audio", "audio/wav")},
        )

    assert repository.created_audio_asset is not None
    assert not list(tmp_path.rglob("*.wav"))


def test_upload_audio_rejects_unknown_project(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)

    response = client.post(
        "/projects/00000000-0000-0000-0000-000000000000/audio",
        files={"file": ("demo.wav", b"RIFFdemo-audio", "audio/wav")},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "project not found"


def test_upload_audio_rejects_unsupported_extension(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)
    project = create_project(client)

    response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.txt", b"not audio", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported audio file extension"
    assert list(tmp_path.rglob("*")) == []


def test_upload_audio_rejects_unsupported_content_type(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)
    project = create_project(client)

    response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.wav", b"RIFFdemo-audio", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported audio content type"
    assert list(tmp_path.rglob("*")) == []


def test_upload_audio_rejects_empty_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path)
    project = create_project(client)

    response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("demo.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "audio file must not be empty"
    assert not list(tmp_path.rglob("*.wav"))


def test_upload_audio_rejects_file_over_size_limit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = create_test_client(monkeypatch, tmp_path, upload_max_mb=1)
    project = create_project(client)
    oversized_payload = b"0" * ((1024 * 1024) + 1)

    response = client.post(
        f"/projects/{project['id']}/audio",
        files={"file": ("large.wav", oversized_payload, "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "audio file exceeds upload size limit"
    assert not list(tmp_path.rglob("*.wav"))


def test_store_audio_upload_rejects_project_path_traversal(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    outside_dir = tmp_path / "outside"
    file = UploadFile(
        file=io.BytesIO(b"RIFFdemo-audio"),
        filename="demo.wav",
        headers=Headers({"content-type": "audio/wav"}),
    )

    with pytest.raises(UploadValidationError, match="invalid storage path"):
        asyncio.run(
            store_audio_upload(
                file=file,
                storage_root=storage_root,
                project_id="../../outside",
                max_bytes=1024,
            )
        )

    assert not outside_dir.exists()
    assert not storage_root.exists()


def test_get_unknown_task_returns_404(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = create_test_client(monkeypatch, tmp_path)

    response = client.get("/tasks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "task not found"
