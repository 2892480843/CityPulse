from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_CSV_ROWS = 200_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CITYPULSE_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = "development"
    debug: bool = False
    app_version: str = "0.1.0"
    log_level: LogLevel = "INFO"
    database_url: str = "postgresql+psycopg://citypulse:citypulse@localhost:5432/citypulse"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: SecretStr = SecretStr("local-development-only-change-me")
    cookie_secure: bool = False
    upload_dir: Path = Path("var/uploads")
    max_upload_bytes: int = MAX_UPLOAD_BYTES
    max_csv_rows: int = MAX_CSV_ROWS
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    audit_retention_days: int = 365
    upload_retention_days: int = 90

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> Self:
        if self.environment != "production":
            return self
        if self.debug:
            raise ValueError("debug must be disabled in production")
        if not self.cookie_secure:
            raise ValueError("secure cookies are required in production")
        if self.session_secret.get_secret_value() == "local-development-only-change-me":
            raise ValueError("replace the development session secret in production")
        if len(self.session_secret.get_secret_value()) < 32:
            raise ValueError("the production session secret must contain at least 32 characters")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
