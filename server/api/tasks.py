from typing import Protocol, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from server.domain.repository import AssetRepository, get_asset_repository
from server.schemas.assets import TranscriptionJobResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskDispatcher(Protocol):
    def send_task(self, name: str, args: list[str]) -> object:
        ...


@router.get("/{job_id}", response_model=TranscriptionJobResponse)
def get_transcription_job(
    job_id: UUID,
    repository: AssetRepository = Depends(get_asset_repository),
) -> TranscriptionJobResponse:
    job = repository.get_transcription_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return TranscriptionJobResponse.model_validate(job)


@router.post("/{job_id}/dispatch", response_model=TranscriptionJobResponse, status_code=status.HTTP_202_ACCEPTED)
def dispatch_transcription_job(
    job_id: UUID,
    request: Request,
    repository: AssetRepository = Depends(get_asset_repository),
) -> TranscriptionJobResponse:
    job = repository.get_transcription_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")

    celery_app = _get_celery_app(request)
    celery_app.send_task("agentclef.transcription.run_baseline", args=[str(job.id)])
    return TranscriptionJobResponse.model_validate(job)


def _get_celery_app(request: Request) -> TaskDispatcher:
    celery_app = getattr(request.app.state, "celery_app", None)
    if not hasattr(celery_app, "send_task"):
        raise RuntimeError("celery app is not initialized")
    return cast(TaskDispatcher, celery_app)
