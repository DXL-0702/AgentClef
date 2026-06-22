from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.health import router as health_router
from server.api.projects import router as projects_router
from server.api.tasks import router as tasks_router
from server.api.uploads import router as uploads_router
from server.config import Settings, get_settings
from server.db import create_database_engine, create_database_schema, create_session_factory
from worker.app import create_celery_app


def create_app(settings: Settings | None = None, *, initialize_database: bool = False) -> FastAPI:
    runtime_settings = settings or get_settings()
    app = FastAPI(title=runtime_settings.app_name, version=runtime_settings.app_version)
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    engine = create_database_engine(runtime_settings)
    if initialize_database:
        create_database_schema(engine)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.celery_app = create_celery_app(runtime_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(uploads_router)
    app.include_router(tasks_router)
    return app
