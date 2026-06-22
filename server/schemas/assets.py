from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AudioAssetStatus(StrEnum):
    uploaded = "uploaded"


class TranscriptionJobStatus(StrEnum):
    created = "created"
    uploaded = "uploaded"
    preprocessing = "preprocessing"
    transcribing = "transcribing"
    postprocessing = "postprocessing"
    draft_ready = "draft_ready"
    upload_failed = "upload_failed"
    preprocessing_failed = "preprocessing_failed"
    transcription_failed = "transcription_failed"
    postprocessing_failed = "postprocessing_failed"


class ProjectCreateRequest(BaseModel):
    title: str = Field(default="Untitled project", max_length=160)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime


class AudioAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    original_filename: str
    content_type: str
    extension: str
    size_bytes: int
    duration_seconds: float
    status: AudioAssetStatus
    created_at: datetime


class TranscriptionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    audio_asset_id: UUID
    status: TranscriptionJobStatus
    created_at: datetime
    updated_at: datetime


class UploadAudioResponse(BaseModel):
    project: ProjectResponse
    audio_asset: AudioAssetResponse
    transcription_job: TranscriptionJobResponse


def utc_now() -> datetime:
    return datetime.now(UTC)
