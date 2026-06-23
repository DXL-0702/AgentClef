import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from server.api.errors import raise_api_error
from server.config import Settings, get_settings
from server.domain.repository import AssetRepository, get_asset_repository
from server.domain.storage import UploadValidationError, delete_stored_upload, store_audio_upload
from server.schemas.assets import (
    AudioAssetResponse,
    ProjectResponse,
    TranscriptionJobResponse,
    UploadAudioResponse,
)

router = APIRouter(prefix="/projects/{project_id}/audio", tags=["uploads"])
logger = logging.getLogger(__name__)


@router.post("", response_model=UploadAudioResponse, status_code=status.HTTP_201_CREATED)
async def upload_audio(
    project_id: UUID,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    repository: AssetRepository = Depends(get_asset_repository),
) -> UploadAudioResponse:
    project = repository.get_project(project_id)
    if project is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="project_not_found",
            message="project not found",
        )

    max_bytes = settings.upload_max_mb * 1024 * 1024
    try:
        stored_upload = await store_audio_upload(
            file=file,
            storage_root=Path(settings.file_storage_path),
            project_id=str(project.id),
            max_bytes=max_bytes,
            max_seconds=settings.upload_max_seconds,
        )
    except UploadValidationError as exc:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="upload_validation_failed",
            message=str(exc),
        )

    try:
        audio_asset, job = repository.create_audio_asset_with_job(
            project_id=project.id,
            original_filename=stored_upload.original_filename,
            stored_filename=stored_upload.stored_filename,
            content_type=stored_upload.content_type,
            extension=stored_upload.extension,
            size_bytes=stored_upload.size_bytes,
            duration_seconds=stored_upload.duration_seconds,
        )
    except Exception:
        try:
            await delete_stored_upload(
                storage_root=Path(settings.file_storage_path),
                project_id=str(project.id),
                stored_filename=stored_upload.stored_filename,
            )
        except Exception:
            logger.exception("failed to delete stored upload after persistence failure")
        raise

    return UploadAudioResponse(
        project=ProjectResponse.model_validate(project),
        audio_asset=AudioAssetResponse.model_validate(audio_asset),
        transcription_job=TranscriptionJobResponse.model_validate(job),
    )
