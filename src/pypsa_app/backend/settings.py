"""Application configuration using environment variables"""

from pathlib import Path
from typing import Self

from platformdirs import user_data_dir
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_V1_PREFIX = "/api/v1"
SESSION_COOKIE_NAME = "pypsa_session"

# Sentinel value: when database_url equals this, it is derived from data_dir.
_DEFAULT_DATABASE_URL_SENTINEL = "__derive_from_data_dir__"

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
    local_mode: bool = Field(
        default=False,
        description=(
            "Single-user local-dashboard deployment (the bare `pypsa-app` CLI). "
            "Enables zero-copy in-place network registration. "
            "Incompatible with ENABLE_AUTH=true."
        ),
        json_schema_extra={"category": "Application"},
    )
    data_dir: str = Field(
        default_factory=lambda: user_data_dir("pypsa-app", "PyPSA"),
        description=(
            "File storage directory to store application data and network files"
        ),
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
        default=_DEFAULT_DATABASE_URL_SENTINEL,
        description=(
            "Database URL (SQLite and PostgreSQL are supported). "
            "Defaults to a SQLite file inside data_dir."
        ),
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
        description=(
            "Secret key for session cookies (generate with: openssl rand -base64 32)"
        ),
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )
    session_ttl: int = Field(
        default=604800,
        description="Session time-to-live in seconds (default: 7 days)",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )

    # Networks
    max_upload_size_mb: int = Field(
        default=2000,
        description="Maximum network file upload size in megabytes",
        json_schema_extra={"category": "Networks"},
    )

    # Runs
    snakedispatch_sync_interval: float = Field(
        default=10.0,
        description="Interval in seconds between background Snakedispatch sync cycles",
        json_schema_extra={"category": "Runs"},
    )
    callback_url_allowed_domains: str = Field(
        default="",
        description=(
            "Comma-separated list of allowed domains for run callback URLs "
            "(e.g. hooks.myorg.dev,example.com). "
            "Callbacks are rejected unless the host matches. "
            "Empty disables callbacks entirely."
        ),
        json_schema_extra={"category": "Runs"},
    )

    @property
    def resolved_callback_domains(self) -> list[str]:
        """Parse CALLBACK_URL_ALLOWED_DOMAINS into a list of domain strings."""
        if not self.callback_url_allowed_domains:
            return []
        return [
            d.strip() for d in self.callback_url_allowed_domains.split(",") if d.strip()
        ]

    snakedispatch_backends: str | None = Field(
        default=None,
        description=(
            "Comma-separated list of Snakedispatch backends in name=url format "
            "(e.g. cluster-a=http://sd-a:8000,cluster-b=http://sd-b:8000)"
        ),
        json_schema_extra={"category": "Runs"},
    )

    @property
    def resolved_backends(self) -> list[dict[str, str]]:
        """Parse SNAKEDISPATCH_BACKENDS into a list of {name, url} dicts."""
        if not self.snakedispatch_backends:
            return []
        backends = []
        for raw_entry in self.snakedispatch_backends.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            if "=" not in entry:
                msg = (
                    f"Invalid SNAKEDISPATCH_BACKENDS entry '{entry}'. "
                    "Expected format: name=url"
                )
                raise ValueError(msg)
            name, url = entry.split("=", 1)
            backends.append({"name": name.strip(), "url": url.strip()})
        return backends

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
    network_cache_ttl: int = Field(
        default=7200,
        description="Time-to-live in seconds for network cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    run_outputs_cache_ttl: int = Field(
        default=10800,
        description="Time-to-live in seconds for run output file list cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    max_cache_size_mb: int = Field(
        default=50,
        description="Maximum cache size in megabytes",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )

    # SMTP
    smtp_host: str | None = Field(
        default=None,
        description="SMTP server hostname (enables email notifications when set)",
        json_schema_extra={"category": "Email"},
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_username: str | None = Field(
        default=None,
        description="SMTP authentication username",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_password: str | None = Field(
        default=None,
        description="SMTP authentication password",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS/STARTTLS for SMTP connection",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_from_address: str = Field(
        default="noreply@pypsa-app.local",
        description="Sender email address for notifications",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )

    @property
    def smtp_enabled(self) -> bool:
        """Whether SMTP email notifications are configured."""
        return self.smtp_host is not None

    # Development
    backend_only: bool = Field(
        default=False,
        description="Run backend only without serving the frontend",
        json_schema_extra={"category": "Development"},
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:5174",
        description=(
            "Comma-separated list of allowed CORS origins"
            " (only used in backend-only mode)"
        ),
        json_schema_extra={"category": "Development", "depends_on": "backend_only"},
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> Self:
        if self.database_url == _DEFAULT_DATABASE_URL_SENTINEL:
            self.database_url = f"sqlite:///{self.data_dir_path}/pypsa-app.db"
        return self

    @model_validator(mode="after")
    def validate_local_mode(self) -> Self:
        if self.local_mode and self.enable_auth:
            msg = (
                "LOCAL_MODE and ENABLE_AUTH cannot both be true. "
                "Local mode is a single-user dashboard deployment."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_auth_settings(self) -> Self:
        if self.enable_auth and self.database_url.startswith("sqlite"):
            msg = (
                "Authentication requires PostgreSQL. "
                "SQLite does not support the features needed for multi-user auth. "
                "Either set ENABLE_AUTH=false or use a PostgreSQL DATABASE_URL."
            )
            raise ValueError(msg)

        if (
            self.enable_auth
            and self.session_secret_key == "dev-secret-key-change-in-production"  # noqa: S105
        ):
            msg = "Must set a secure SESSION_SECRET_KEY when authentication is enabled"
            raise ValueError(msg)
        return self


settings = Settings()
