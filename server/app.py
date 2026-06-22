from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.health import router as health_router
from server.api.projects import router as projects_router
from server.api.tasks import router as tasks_router
from server.api.uploads import router as uploads_router
from server.config import Settings, get_settings
from server.domain.repository import AssetRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    app = FastAPI(title=runtime_settings.app_name, version=runtime_settings.app_version)
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    app.state.repository = AssetRepository()
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
