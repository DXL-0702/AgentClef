from pathlib import Path

from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import create_engine, inspect

from server.db import create_database_engine, create_database_schema, create_session_factory
from server.domain.repository import SqlAlchemyAssetRepository
from server.models import AudioAssetRecord
from server.schemas.assets import ProjectCreateRequest
from tests.settings_helpers import make_settings


EXPECTED_CORE_TABLES = {
    "agent_messages",
    "audio_assets",
    "candidate_edits",
    "draft_scores",
    "projects",
    "revisions",
    "transcription_jobs",
}


def sqlite_file_dsn(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def test_alembic_upgrade_creates_v01_core_tables(tmp_path: Path) -> None:
    dsn = sqlite_file_dsn(tmp_path / "migration.db")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", dsn)

    command.upgrade(config, "head")

    engine = create_engine(dsn)
    inspector = inspect(engine)
    assert EXPECTED_CORE_TABLES.issubset(set(inspector.get_table_names()))
    audio_asset_columns = {column["name"] for column in inspector.get_columns("audio_assets")}
    assert "duration_seconds" in audio_asset_columns
    orm_audio_asset_columns = {column.name for column in AudioAssetRecord.__table__.columns}
    assert audio_asset_columns == orm_audio_asset_columns


def test_sqlalchemy_repository_persists_upload_foundation_records(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = make_settings(
        monkeypatch,
        postgres_dsn=sqlite_file_dsn(tmp_path / "repository.db"),
    )
    engine = create_database_engine(settings)
    create_database_schema(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        project = repository.create_project(ProjectCreateRequest(title="Persistent upload"))

    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        persisted_project = repository.get_project(project.id)
        assert persisted_project == project
        audio_asset, job = repository.create_audio_asset_with_job(
            project_id=project.id,
            original_filename="demo.wav",
            stored_filename="stored-demo.wav",
            content_type="audio/wav",
            extension=".wav",
            size_bytes=128,
            duration_seconds=0.25,
        )

    with session_factory() as session:
        repository = SqlAlchemyAssetRepository(session)
        persisted_job = repository.get_transcription_job(job.id)
        assert persisted_job == job
        assert persisted_job is not None
        assert persisted_job.audio_asset_id == audio_asset.id
        assert audio_asset.duration_seconds == 0.25
