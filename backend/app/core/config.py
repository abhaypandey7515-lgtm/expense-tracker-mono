"""Application configuration (environment variables / .env)."""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "Expense Tracker"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Async SQLite through SQLAlchemy + aiosqlite
    DATABASE_URL: str = "sqlite+aiosqlite:///./expense_tracker.db"

    # Authentication
    SESSION_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    PBKDF2_ITERATIONS: int = 200_000

    # The TUI is not a browser, so CORS is off unless a web client is added.
    BACKEND_CORS_ORIGINS: List[str] = []


settings = Settings()
