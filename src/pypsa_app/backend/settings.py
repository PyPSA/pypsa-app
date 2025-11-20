"""Application configuration using environment variables"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Base URL (publicly accessible URL of the application)
    base_url: str = "http://localhost:5173"

    # Mode flags
    serve_frontend: bool = True

    # API
    api_v1_prefix: str = "/api/v1"

    # Storage
    data_dir: str = "./data"

    @property
    def data_dir_path(self) -> Path:
        """Computed absolute path to data directory"""
        return Path(self.data_dir).resolve()

    # Database
    database_url: str = "sqlite:///./data/pypsa-app.db"

    @property
    def networks_path(self) -> Path:
        """Computed path to networks directory"""
        return self.data_dir_path / "networks"

    # Connection pool settings (PostgreSQL only, ignored for SQLite)
    db_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600

    # CORS
    # only relevant when serve_frontend is False
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    # Redis (optional)
    redis_url: str | None = None
    plot_cache_ttl: int = 86400
    map_cache_ttl: int = 3600
    network_cache_ttl: int = 7200
    max_cache_size_mb: int = 50

    # Authentication
    enable_auth: bool = False
    github_client_id: str | None = None
    github_client_secret: str | None = None
    session_secret_key: str = "dev-secret-key-change-in-production"
    session_cookie_name: str = "pypsa_session"
    session_ttl: int = 604800  # 7 days in seconds


settings = Settings()
