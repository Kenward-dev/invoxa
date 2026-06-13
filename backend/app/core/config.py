"""Runtime settings loaded from environment variables and defaults."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings backed by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Invoicio"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite:///./invoicio_dev.db"

    UPLOADS_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE_MB: int = 5

    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value: bool | str) -> bool | str:
        """Treat release-mode debug values from parent shells as disabled."""
        if isinstance(value, str) and value.lower() == "release":
            return False
        return value

    @property
    def is_sqlite(self) -> bool:
        """Return whether the configured database URL targets SQLite."""
        return "sqlite" in self.DATABASE_URL

    @property
    def is_production(self) -> bool:
        """Return whether the app is running in the production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def uploads_path(self) -> Path:
        """Ensure the uploads directory exists and return its path."""
        path = self.UPLOADS_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings for dependency-free imports."""
    return Settings()
