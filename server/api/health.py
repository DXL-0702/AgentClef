from fastapi import APIRouter
from pydantic import BaseModel

from server.config import get_settings

router = APIRouter(tags=["health"])


class UploadLimits(BaseModel):
    max_mb: int
    max_seconds: int


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    postgres_configured: bool
    redis_configured: bool
    file_storage_configured: bool
    upload_limits: UploadLimits
    llm_provider: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        postgres_configured=bool(settings.postgres_dsn),
        redis_configured=bool(settings.redis_url),
        file_storage_configured=bool(settings.file_storage_path),
        upload_limits=UploadLimits(
            max_mb=settings.upload_max_mb,
            max_seconds=settings.upload_max_seconds,
        ),
        llm_provider=settings.llm_provider,
    )
