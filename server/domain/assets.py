from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from server.schemas.assets import AudioAssetStatus, TranscriptionJobStatus


@dataclass(frozen=True)
class Project:
    id: UUID
    title: str
    created_at: datetime


@dataclass(frozen=True)
class AudioAsset:
    id: UUID
    project_id: UUID
    original_filename: str
    stored_filename: str
    content_type: str
    extension: str
    size_bytes: int
    duration_seconds: float
    status: AudioAssetStatus
    created_at: datetime


@dataclass(frozen=True)
class TranscriptionJob:
    id: UUID
    project_id: UUID
    audio_asset_id: UUID
    status: TranscriptionJobStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DraftScore:
    id: UUID
    project_id: UUID
    transcription_job_id: UUID | None
    version: int
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
