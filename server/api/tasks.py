from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from server.domain.repository import AssetRepository, get_asset_repository
from server.schemas.assets import TranscriptionJobResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{job_id}", response_model=TranscriptionJobResponse)
def get_transcription_job(
    job_id: UUID,
    repository: AssetRepository = Depends(get_asset_repository),
) -> TranscriptionJobResponse:
    job = repository.get_transcription_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return TranscriptionJobResponse.model_validate(job)
