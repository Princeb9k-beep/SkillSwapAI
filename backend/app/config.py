"""
Application configuration.

Loads settings from environment variables (and a local `.env` during development)
using pydantic-settings. Centralizing config here keeps the rest of the app free of
`os.getenv` calls and gives us one typed, validated source of truth.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- PostgreSQL -------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "skillswapaidb"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    # A full URL (e.g. Render's connection string) takes precedence when set.
    database_url: str = ""

    # --- Redis ------------------------------------------------------------
    redis_url: str = "redis://localhost:6379"
    redis_password: str = ""

    # --- Groq AI ----------------------------------------------------------
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # --- App --------------------------------------------------------------
    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_debug: bool = False
    cors_origins: str = "*"

    # AI/cache tuning
    ai_cache_ttl_seconds: int = 60 * 60 * 24      # cache AI responses for a day
    lock_ttl_ms: int = 30_000                     # distributed lock lease

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def async_database_url(self) -> str:
        """Return a SQLAlchemy async URL, normalizing common Render formats."""
        if self.database_url:
            url = self.database_url
            # Render exposes `postgres://...`; SQLAlchemy needs the async driver.
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed only once per process."""
    return Settings()
