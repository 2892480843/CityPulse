from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


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
