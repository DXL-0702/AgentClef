import asyncio
import io
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from starlette.datastructures import Headers

from server.app import create_app
from server.domain.assets import AudioAsset, Project, TranscriptionJob
from server.domain.repository import get_asset_repository
from server.domain.storage import UploadValidationError, store_audio_upload
from server.schemas.assets import AudioAssetStatus, ProjectCreateRequest, utc_now
from tests.settings_helpers import make_settings


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
