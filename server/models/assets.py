from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeEngine, Uuid

from server.models.base import Base


def json_payload_type() -> TypeEngine[Any]:
    return JSON().with_variant(JSONB(), "postgresql")


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AudioAssetRecord(Base):
    __tablename__ = "audio_assets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TranscriptionJobRecord(Base):
    __tablename__ = "transcription_jobs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    audio_asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audio_assets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DraftScoreRecord(Base):
    __tablename__ = "draft_scores"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    transcription_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transcription_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(json_payload_type(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentMessageRecord(Base):
    __tablename__ = "agent_messages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    draft_score_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("draft_scores.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_payload: Mapped[dict[str, Any]] = mapped_column(json_payload_type(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CandidateEditRecord(Base):
    __tablename__ = "candidate_edits"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    draft_score_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("draft_scores.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(json_payload_type(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RevisionRecord(Base):
    __tablename__ = "revisions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    draft_score_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("draft_scores.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    candidate_edit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidate_edits.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(json_payload_type(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
