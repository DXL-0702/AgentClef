from collections.abc import Collection, Iterator
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from server.domain.assets import AudioAsset, DraftScore, Project, TranscriptionJob
from server.models import AudioAssetRecord, DraftScoreRecord, ProjectRecord, TranscriptionJobRecord
from server.schemas.assets import (
    AudioAssetStatus,
    ProjectCreateRequest,
    TranscriptionJobStatus,
    utc_now,
)


class AssetRepository(Protocol):
    def create_project(self, payload: ProjectCreateRequest) -> Project:
        ...

    def get_project(self, project_id: UUID) -> Project | None:
        ...

    def create_audio_asset(
        self,
        *,
        project_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
        duration_seconds: float,
    ) -> AudioAsset:
        ...

    def get_audio_asset(self, audio_asset_id: UUID) -> AudioAsset | None:
        ...

    def create_transcription_job(
        self, project_id: UUID, audio_asset_id: UUID
    ) -> TranscriptionJob:
        ...

    def create_audio_asset_with_job(
        self,
        *,
        project_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
        duration_seconds: float,
    ) -> tuple[AudioAsset, TranscriptionJob]:
        ...

    def get_transcription_job(self, job_id: UUID) -> TranscriptionJob | None:
        ...

    def update_transcription_job_status(
        self,
        job_id: UUID,
        status: TranscriptionJobStatus,
    ) -> TranscriptionJob | None:
        ...

    def claim_transcription_job_for_dispatch(
        self,
        job_id: UUID,
        allowed_statuses: Collection[TranscriptionJobStatus],
        target_status: TranscriptionJobStatus,
    ) -> tuple[TranscriptionJob, TranscriptionJobStatus] | None:
        ...

    def create_draft_score(
        self,
        *,
        draft_score_id: UUID,
        project_id: UUID,
        transcription_job_id: UUID,
        version: int,
        payload: dict[str, Any],
    ) -> DraftScore:
        ...

    def get_draft_score_for_job(self, job_id: UUID) -> DraftScore | None:
        ...


class SqlAlchemyAssetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_project(self, payload: ProjectCreateRequest) -> Project:
        record = ProjectRecord(
            id=uuid4(),
            title=payload.title,
            created_at=utc_now(),
        )
        self._session.add(record)
        self._commit_and_refresh_if_needed(record)
        return _project_from_record(record)

    def get_project(self, project_id: UUID) -> Project | None:
        record = self._session.get(ProjectRecord, project_id)
        return _project_from_record(record) if record is not None else None

    def create_audio_asset(
        self,
        *,
        project_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
        duration_seconds: float,
    ) -> AudioAsset:
        record = self._build_audio_asset_record(
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            extension=extension,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
        )
        self._session.add(record)
        self._commit_and_refresh_if_needed(record)
        return _audio_asset_from_record(record)

    def get_audio_asset(self, audio_asset_id: UUID) -> AudioAsset | None:
        record = self._session.get(AudioAssetRecord, audio_asset_id)
        return _audio_asset_from_record(record) if record is not None else None

    def create_transcription_job(self, project_id: UUID, audio_asset_id: UUID) -> TranscriptionJob:
        record = _build_transcription_job_record(project_id, audio_asset_id)
        self._session.add(record)
        self._commit_and_refresh_if_needed(record)
        return _transcription_job_from_record(record)

    def create_audio_asset_with_job(
        self,
        *,
        project_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
        duration_seconds: float,
    ) -> tuple[AudioAsset, TranscriptionJob]:
        audio_asset_record = self._build_audio_asset_record(
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            extension=extension,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
        )
        job_record = _build_transcription_job_record(project_id, audio_asset_record.id)
        self._session.add_all([audio_asset_record, job_record])
        self._commit_and_refresh_if_needed(audio_asset_record, job_record)
        return _audio_asset_from_record(audio_asset_record), _transcription_job_from_record(
            job_record
        )

    def get_transcription_job(self, job_id: UUID) -> TranscriptionJob | None:
        record = self._session.get(TranscriptionJobRecord, job_id)
        return _transcription_job_from_record(record) if record is not None else None

    def update_transcription_job_status(
        self,
        job_id: UUID,
        status: TranscriptionJobStatus,
    ) -> TranscriptionJob | None:
        record = self._session.get(TranscriptionJobRecord, job_id)
        if record is None:
            return None
        record.status = status.value
        record.updated_at = utc_now()
        self._commit_and_refresh_if_needed(record)
        return _transcription_job_from_record(record)

    def claim_transcription_job_for_dispatch(
        self,
        job_id: UUID,
        allowed_statuses: Collection[TranscriptionJobStatus],
        target_status: TranscriptionJobStatus,
    ) -> tuple[TranscriptionJob, TranscriptionJobStatus] | None:
        record = self._session.get(TranscriptionJobRecord, job_id)
        if record is None:
            return None

        previous_status = TranscriptionJobStatus(record.status)
        updated_at = utc_now()
        statement = (
            update(TranscriptionJobRecord)
            .where(
                TranscriptionJobRecord.id == job_id,
                TranscriptionJobRecord.status.in_([status.value for status in allowed_statuses]),
            )
            .values(status=target_status.value, updated_at=updated_at)
            .execution_options(synchronize_session=False)
        )
        try:
            result = cast(CursorResult[Any], self._session.execute(statement))
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise
        if result.rowcount != 1:
            self._session.expire_all()
            return None

        claimed_job = TranscriptionJob(
            id=record.id,
            project_id=record.project_id,
            audio_asset_id=record.audio_asset_id,
            status=target_status,
            created_at=record.created_at,
            updated_at=updated_at,
        )
        self._session.expire(record)
        return claimed_job, previous_status

    def create_draft_score(
        self,
        *,
        draft_score_id: UUID,
        project_id: UUID,
        transcription_job_id: UUID,
        version: int,
        payload: dict[str, Any],
    ) -> DraftScore:
        now = utc_now()
        record = DraftScoreRecord(
            id=draft_score_id,
            project_id=project_id,
            transcription_job_id=transcription_job_id,
            version=version,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._commit_and_refresh_if_needed(record)
        return _draft_score_from_record(record)

    def get_draft_score_for_job(self, job_id: UUID) -> DraftScore | None:
        record = (
            self._session.query(DraftScoreRecord)
            .filter(DraftScoreRecord.transcription_job_id == job_id)
            .order_by(DraftScoreRecord.version.desc(), DraftScoreRecord.created_at.desc())
            .first()
        )
        return _draft_score_from_record(record) if record is not None else None

    def _build_audio_asset_record(
        self,
        *,
        project_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
        duration_seconds: float,
    ) -> AudioAssetRecord:
        return AudioAssetRecord(
            id=uuid4(),
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            extension=extension,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
            status=AudioAssetStatus.uploaded.value,
            created_at=utc_now(),
        )

    def _commit_and_refresh_if_needed(self, *records: object) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise
        if self._session.get_bind().dialect.name == "sqlite":
            for record in records:
                self._session.refresh(record)


def _build_transcription_job_record(
    project_id: UUID, audio_asset_id: UUID
) -> TranscriptionJobRecord:
    now = utc_now()
    return TranscriptionJobRecord(
        id=uuid4(),
        project_id=project_id,
        audio_asset_id=audio_asset_id,
        status=TranscriptionJobStatus.uploaded.value,
        created_at=now,
        updated_at=now,
    )


def _project_from_record(record: ProjectRecord) -> Project:
    return Project(
        id=record.id,
        title=record.title,
        created_at=record.created_at,
    )


def _audio_asset_from_record(record: AudioAssetRecord) -> AudioAsset:
    return AudioAsset(
        id=record.id,
        project_id=record.project_id,
        original_filename=record.original_filename,
        stored_filename=record.stored_filename,
        content_type=record.content_type,
        extension=record.extension,
        size_bytes=record.size_bytes,
        duration_seconds=record.duration_seconds,
        status=AudioAssetStatus(record.status),
        created_at=record.created_at,
    )


def _transcription_job_from_record(record: TranscriptionJobRecord) -> TranscriptionJob:
    return TranscriptionJob(
        id=record.id,
        project_id=record.project_id,
        audio_asset_id=record.audio_asset_id,
        status=TranscriptionJobStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _draft_score_from_record(record: DraftScoreRecord) -> DraftScore:
    return DraftScore(
        id=record.id,
        project_id=record.project_id,
        transcription_job_id=record.transcription_job_id,
        version=record.version,
        payload=record.payload,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def get_asset_repository(request: Request) -> Iterator[AssetRepository]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("database session factory is not initialized")
    with session_factory() as session:
        yield SqlAlchemyAssetRepository(session)
