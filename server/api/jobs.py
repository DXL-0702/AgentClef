import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import StreamingResponse

from server.api.errors import raise_api_error
from server.db import SessionFactory
from server.domain.repository import SqlAlchemyAssetRepository
from server.schemas.assets import TranscriptionJobResponse, TranscriptionJobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])

TERMINAL_JOB_STATUSES: frozenset[TranscriptionJobStatus] = frozenset(
    {
        TranscriptionJobStatus.draft_ready,
        TranscriptionJobStatus.upload_failed,
        TranscriptionJobStatus.preprocessing_failed,
        TranscriptionJobStatus.transcription_failed,
        TranscriptionJobStatus.postprocessing_failed,
    }
)


@router.get("/{job_id}", response_model=TranscriptionJobResponse)
def get_transcription_job(
    job_id: UUID,
    request: Request,
) -> TranscriptionJobResponse:
    job = _load_job_response(request, job_id)
    if job is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="job not found",
        )
    return job


@router.get("/{job_id}/events")
def stream_transcription_job_events(
    job_id: UUID,
    request: Request,
    poll_interval_seconds: float = Query(default=1.0, ge=0.1, le=10.0),
    max_events: int | None = Query(default=None, ge=1, le=100),
) -> StreamingResponse:
    if _load_job_response(request, job_id) is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="job not found",
        )

    return StreamingResponse(
        _iter_job_status_events(
            request=request,
            job_id=job_id,
            poll_interval_seconds=poll_interval_seconds,
            max_events=max_events,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def _iter_job_status_events(
    *,
    request: Request,
    job_id: UUID,
    poll_interval_seconds: float,
    max_events: int | None,
) -> AsyncIterator[str]:
    sent_events = 0
    while True:
        job = _load_job_response(request, job_id)
        if job is None:
            yield _format_sse_event(
                "job_missing",
                {"job_id": str(job_id), "status": "missing"},
            )
            break

        payload = job.model_dump(mode="json")
        yield _format_sse_event("job_status", payload)
        sent_events += 1

        if job.status in TERMINAL_JOB_STATUSES:
            break
        if max_events is not None and sent_events >= max_events:
            break
        await asyncio.sleep(poll_interval_seconds)


def _load_job_response(request: Request, job_id: UUID) -> TranscriptionJobResponse | None:
    session_factory = _get_session_factory(request)
    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        job = repository.get_transcription_job(job_id)
    if job is None:
        return None
    return TranscriptionJobResponse.model_validate(job)


def _get_session_factory(request: Request) -> SessionFactory:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("database session factory is not initialized")
    return session_factory


def _format_sse_event(event_name: str, payload: dict[str, object]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
