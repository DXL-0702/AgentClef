from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from server.config import Settings
from server.models import Base


SessionFactory = sessionmaker[Session]


def create_database_engine(settings: Settings) -> Engine:
    connect_args: dict[str, object] = {}
    if settings.postgres_dsn.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if settings.postgres_dsn == "sqlite+pysqlite:///:memory:":
        return create_engine(
            settings.postgres_dsn,
            connect_args=connect_args,
            pool_pre_ping=True,
            poolclass=StaticPool,
        )
    return create_engine(
        settings.postgres_dsn,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_database_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
