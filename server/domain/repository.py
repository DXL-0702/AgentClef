from threading import Lock
from uuid import UUID, uuid4

from fastapi import Request

from server.domain.assets import AudioAsset, Project, TranscriptionJob
from server.schemas.assets import (
    AudioAssetStatus,
    ProjectCreateRequest,
    TranscriptionJobStatus,
    utc_now,
)


class AssetRepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self._projects: dict[UUID, Project] = {}
        self._audio_assets: dict[UUID, AudioAsset] = {}
        self._jobs: dict[UUID, TranscriptionJob] = {}

    def create_project(self, payload: ProjectCreateRequest) -> Project:
        now = utc_now()
        project = Project(
            id=uuid4(),
            title=payload.title,
            created_at=now,
        )
        with self._lock:
            self._projects[project.id] = project
        return project

    def get_project(self, project_id: UUID) -> Project | None:
        with self._lock:
            return self._projects.get(project_id)

    def create_audio_asset(
        self,
        *,
        project_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
    ) -> AudioAsset:
        now = utc_now()
        audio_asset = AudioAsset(
            id=uuid4(),
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            extension=extension,
            size_bytes=size_bytes,
            status=AudioAssetStatus.uploaded,
            created_at=now,
        )
        with self._lock:
            self._audio_assets[audio_asset.id] = audio_asset
        return audio_asset

    def create_transcription_job(self, project_id: UUID, audio_asset_id: UUID) -> TranscriptionJob:
        now = utc_now()
        job = TranscriptionJob(
            id=uuid4(),
            project_id=project_id,
            audio_asset_id=audio_asset_id,
            status=TranscriptionJobStatus.uploaded,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get_transcription_job(self, job_id: UUID) -> TranscriptionJob | None:
        with self._lock:
            return self._jobs.get(job_id)


def get_asset_repository(request: Request) -> AssetRepository:
    repository = getattr(request.app.state, "repository", None)
    if not isinstance(repository, AssetRepository):
        raise RuntimeError("asset repository is not initialized")
    return repository
