from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from server.config import Settings, get_settings
from server.domain.repository import AssetRepository, get_asset_repository
from server.domain.storage import UploadValidationError, store_audio_upload
from server.schemas.assets import (
    AudioAssetResponse,
    ProjectResponse,
    TranscriptionJobResponse,
    UploadAudioResponse,
)

router = APIRouter(prefix="/projects/{project_id}/audio", tags=["uploads"])


@router.post("", response_model=UploadAudioResponse, status_code=status.HTTP_201_CREATED)
async def upload_audio(
    project_id: UUID,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    repository: AssetRepository = Depends(get_asset_repository),
) -> UploadAudioResponse:
    project = repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    max_bytes = settings.upload_max_mb * 1024 * 1024
    try:
        stored_upload = await store_audio_upload(
            file=file,
            storage_root=Path(settings.file_storage_path),
            project_id=str(project.id),
            max_bytes=max_bytes,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audio_asset = repository.create_audio_asset(
        project_id=project.id,
        original_filename=stored_upload.original_filename,
        stored_filename=stored_upload.stored_filename,
        content_type=stored_upload.content_type,
        extension=stored_upload.extension,
        size_bytes=stored_upload.size_bytes,
    )
    job = repository.create_transcription_job(project_id=project.id, audio_asset_id=audio_asset.id)

    return UploadAudioResponse(
        project=ProjectResponse.model_validate(project),
        audio_asset=AudioAssetResponse.model_validate(audio_asset),
        transcription_job=TranscriptionJobResponse.model_validate(job),
    )
