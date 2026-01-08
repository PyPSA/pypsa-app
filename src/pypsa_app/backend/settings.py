"""Application configuration using environment variables"""

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_V1_PREFIX = "/api/v1"
SESSION_COOKIE_NAME = "pypsa_session"

# Database pool settings (PostgreSQL only)
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 30
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 3600


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    base_url: str = Field(
        default="http://localhost:5173",
        description="Publicly accessible URL of the application",
        json_schema_extra={"category": "Application"},
    )
    data_dir: str = Field(
        default="./data",
        description="File storage directory to store application data and network files",
        json_schema_extra={"category": "Application"},
    )

    @property
    def data_dir_path(self) -> Path:
        """Computed absolute path to data directory"""
        return Path(self.data_dir).resolve()

    @property
    def networks_path(self) -> Path:
        """Computed path to networks directory"""
        return self.data_dir_path / "networks"

    # Database
    database_url: str = Field(
        default="sqlite:///./data/pypsa-app.db",
        description="Database URL (SQLite and PostgreSQL is supported)",
        json_schema_extra={"category": "Database"},
    )

    # Authentication
    enable_auth: bool = Field(
        default=False,
        description="Enable GitHub OAuth authentication",
        json_schema_extra={"category": "Authentication"},
    )
    github_client_id: str | None = Field(
        default=None,
        description="GitHub OAuth app client ID (create at https://github.com/settings/developers)",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )
    github_client_secret: str | None = Field(
        default=None,
        description="GitHub OAuth app client secret",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )
    session_secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for session cookies (generate with: openssl rand -base64 32)",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )
    session_ttl: int = Field(
        default=604800,
        description="Session time-to-live in seconds (default: 7 days)",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )

    # Map
    mapbox_token: str | None = Field(
        default=None,
        description="Mapbox access token for interactive network map via kepler.gl",
        json_schema_extra={"category": "Map"},
    )

    # Caching
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL for caching (optional)",
        json_schema_extra={"category": "Redis"},
    )
    plot_cache_ttl: int = Field(
        default=86400,
        description="Time-to-live in seconds for plot cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    map_cache_ttl: int = Field(
        default=3600,
        description="Time-to-live in seconds for map cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    network_cache_ttl: int = Field(
        default=7200,
        description="Time-to-live in seconds for network cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    max_cache_size_mb: int = Field(
        default=50,
        description="Maximum cache size in megabytes",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )

    # Development
    backend_only: bool = Field(
        default=False,
        description="Run backend only without serving the frontend",
        json_schema_extra={"category": "Development"},
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:5174",
        description="Comma-separated list of allowed CORS origins (only used in backend-only mode)",
        json_schema_extra={"category": "Development", "depends_on": "backend_only"},
    )

    @model_validator(mode="after")
    def validate_auth_settings(self):
        if self.enable_auth and self.database_url.startswith("sqlite"):
            raise ValueError(
                "Authentication requires PostgreSQL. "
                "SQLite does not support the features needed for multi-user auth. "
                "Either set ENABLE_AUTH=false or use a PostgreSQL DATABASE_URL."
            )

        if (
            self.enable_auth
            and self.session_secret_key == "dev-secret-key-change-in-production"
        ):
            raise ValueError(
                "Must set a secure SESSION_SECRET_KEY when authentication is enabled"
            )
        return self


settings = Settings()
