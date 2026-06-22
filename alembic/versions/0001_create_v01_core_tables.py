"""create v0.1 core tables

Revision ID: 0001_create_v01
Revises:
Create Date: 2026-06-22
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeEngine

revision: str = "0001_create_v01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def json_payload_type() -> TypeEngine[Any]:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audio_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("extension", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
    )
    op.create_index("ix_audio_assets_project_id", "audio_assets", ["project_id"])
    op.create_table(
        "transcription_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("audio_asset_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audio_asset_id"], ["audio_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcription_jobs_audio_asset_id", "transcription_jobs", ["audio_asset_id"])
    op.create_index("ix_transcription_jobs_project_id", "transcription_jobs", ["project_id"])
    op.create_table(
        "draft_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("transcription_job_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", json_payload_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transcription_job_id"], ["transcription_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_draft_scores_project_id", "draft_scores", ["project_id"])
    op.create_index(
        "ix_draft_scores_transcription_job_id",
        "draft_scores",
        ["transcription_job_id"],
    )
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("draft_score_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_payload", json_payload_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_score_id"], ["draft_scores.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_messages_project_id", "agent_messages", ["project_id"])
    op.create_index("ix_agent_messages_draft_score_id", "agent_messages", ["draft_score_id"])
    op.create_table(
        "candidate_edits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("draft_score_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=48), nullable=False),
        sa.Column("payload", json_payload_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_score_id"], ["draft_scores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_edits_draft_score_id", "candidate_edits", ["draft_score_id"])
    op.create_index("ix_candidate_edits_project_id", "candidate_edits", ["project_id"])
    op.create_table(
        "revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("draft_score_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_edit_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=48), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("payload", json_payload_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_edit_id"], ["candidate_edits.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["draft_score_id"], ["draft_scores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revisions_draft_score_id", "revisions", ["draft_score_id"])
    op.create_index("ix_revisions_project_id", "revisions", ["project_id"])
    op.create_index("ix_revisions_candidate_edit_id", "revisions", ["candidate_edit_id"])


def downgrade() -> None:
    op.drop_index("ix_revisions_candidate_edit_id", table_name="revisions")
    op.drop_index("ix_revisions_project_id", table_name="revisions")
    op.drop_index("ix_revisions_draft_score_id", table_name="revisions")
    op.drop_table("revisions")
    op.drop_index("ix_candidate_edits_project_id", table_name="candidate_edits")
    op.drop_index("ix_candidate_edits_draft_score_id", table_name="candidate_edits")
    op.drop_table("candidate_edits")
    op.drop_index("ix_agent_messages_draft_score_id", table_name="agent_messages")
    op.drop_index("ix_agent_messages_project_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_draft_scores_transcription_job_id", table_name="draft_scores")
    op.drop_index("ix_draft_scores_project_id", table_name="draft_scores")
    op.drop_table("draft_scores")
    op.drop_index("ix_transcription_jobs_project_id", table_name="transcription_jobs")
    op.drop_index("ix_transcription_jobs_audio_asset_id", table_name="transcription_jobs")
    op.drop_table("transcription_jobs")
    op.drop_index("ix_audio_assets_project_id", table_name="audio_assets")
    op.drop_table("audio_assets")
    op.drop_table("projects")
