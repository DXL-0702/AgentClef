from functools import lru_cache
from typing import Any, cast

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


def parse_cors_origins_env(value: str) -> list[str] | None:
    normalized = value.strip()
    if not normalized or normalized.startswith("["):
        return None
    return [origin.strip() for origin in normalized.split(",") if origin.strip()]


class CorsOriginsSettingsSourceMixin:
    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "cors_origins" and isinstance(value, str):
            parsed = parse_cors_origins_env(value)
            if parsed is not None:
                return parsed
        return cast(Any, super()).prepare_field_value(field_name, field, value, value_is_complex)


class AgentClefEnvSettingsSource(CorsOriginsSettingsSourceMixin, EnvSettingsSource):
    pass


class AgentClefDotEnvSettingsSource(CorsOriginsSettingsSourceMixin, DotEnvSettingsSource):
    pass


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            AgentClefEnvSettingsSource(settings_cls),
            AgentClefDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )

    @field_validator(
        "app_name",
        "app_version",
        "postgres_dsn",
        "redis_url",
        "file_storage_path",
        "llm_provider",
    )
    @classmethod
    def validate_required_string(cls, value: str, info: ValidationInfo) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} must not be empty")
        return normalized

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        origins = [origin.strip() for origin in value]
        if any(not origin for origin in origins):
            raise ValueError("cors_origins must not contain empty values")
        if "*" in origins:
            raise ValueError("cors_origins must not contain '*' when credentials are enabled")
        return origins

    @field_validator("llm_provider")
    @classmethod
    def normalize_llm_provider(cls, value: str) -> str:
        return value.lower()

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def normalize_llm_api_key(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_llm_credentials(self) -> "Settings":
        if self.llm_provider != "disabled" and self.llm_api_key is None:
            raise ValueError("llm_api_key must be provided when llm_provider is enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
