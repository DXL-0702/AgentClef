"""add audio asset duration

Revision ID: 0002_audio_asset_duration
Revises: 0001_create_v01
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_audio_asset_duration"
down_revision: str | None = "0001_create_v01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audio_assets") as batch_op:
        batch_op.add_column(sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0"))
        batch_op.alter_column(
            "duration_seconds",
            existing_type=sa.Float(),
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("audio_assets") as batch_op:
        batch_op.drop_column("duration_seconds")
