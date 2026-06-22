from typing import Protocol, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from server.domain.repository import AssetRepository, get_asset_repository
from server.schemas.assets import TranscriptionJobResponse, TranscriptionJobStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])

DISPATCHABLE_JOB_STATUSES = {
    TranscriptionJobStatus.uploaded,
    TranscriptionJobStatus.preprocessing_failed,
    TranscriptionJobStatus.transcription_failed,
    TranscriptionJobStatus.postprocessing_failed,
}


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
    celery_app = _get_celery_app(request)
    claim = repository.claim_transcription_job_for_dispatch(
        job_id,
        allowed_statuses=DISPATCHABLE_JOB_STATUSES,
        target_status=TranscriptionJobStatus.preprocessing,
    )
    if claim is None:
        job = repository.get_transcription_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"cannot dispatch task in status: {job.status.value}",
        )
    updated_job, previous_status = claim

    try:
        celery_app.send_task("agentclef.transcription.run_baseline", args=[str(updated_job.id)])
    except Exception:
        repository.update_transcription_job_status(job_id, previous_status)
        raise
    return TranscriptionJobResponse.model_validate(updated_job)


def _get_celery_app(request: Request) -> TaskDispatcher:
    celery_app = getattr(request.app.state, "celery_app", None)
    if not hasattr(celery_app, "send_task"):
        raise RuntimeError("celery app is not initialized")
    return cast(TaskDispatcher, celery_app)
