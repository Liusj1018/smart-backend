"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Smart Commit Backend"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    debug: bool = True

    # Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database — async PostgreSQL via asyncpg
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/smart_commit"

    # CORS whitelist — comma-separated in env, NEVER use "*" in production
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,"
        "https://smart-commit-helper-2-0.vercel.app"
    )

    # JWT configuration
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        """Return the database URL normalized to the asyncpg driver.

        PaaS providers (e.g. Railway) often set ``DATABASE_URL=postgresql://...``
        which SQLAlchemy resolves to the synchronous psycopg2 driver. The async
        engine and Alembic require ``postgresql+asyncpg://``.
        """
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql+psycopg://"):
            return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
