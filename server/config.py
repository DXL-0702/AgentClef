from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENTCLEF_",
        extra="ignore",
    )

    app_name: str = "AgentClef"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_port: int = Field(default=8000, ge=1, le=65535)
    postgres_dsn: str = "postgresql+psycopg://agentclef:agentclef@localhost:5432/agentclef"
    redis_url: str = "redis://localhost:6379/0"
    file_storage_path: str = "./storage"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    upload_max_mb: int = Field(default=50, gt=0)
    upload_max_seconds: int = Field(default=300, gt=0)
    llm_provider: str = "disabled"
    llm_api_key: str | None = None

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
