"""SQLAlchemy database models"""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from pypsa_app.backend.database import Base


def str_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Create SQLAlchemy Enum that stores enum values as native PostgreSQL enum."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


user_backends = Table(
    "user_backends",
    Base.metadata,
    Column(
        "user_id",
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "backend_id",
        Uuid,
        ForeignKey("snakedispatch_backends.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SnakedispatchBackend(Base):
    """A registered Snakedispatch execution backend."""

    __tablename__ = "snakedispatch_backends"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str] = mapped_column(String(512), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )

    users: Mapped[list["User"]] = relationship(
        secondary=user_backends, back_populates="backends"
    )


class UserRole(enum.StrEnum):
    """User roles for access control"""

    ADMIN = "admin"
    USER = "user"
    BOT = "bot"
    PENDING = "pending"


class Permission(enum.StrEnum):
    """Permission constants for access control. Format: resource:action"""

    # Network permissions
    NETWORKS_VIEW = "networks:view"
    NETWORKS_MODIFY = "networks:modify"
    NETWORKS_MANAGE_ALL = "networks:manage_all"

    # Run permissions
    RUNS_VIEW = "runs:view"
    RUNS_MODIFY = "runs:modify"
    RUNS_MANAGE_ALL = "runs:manage_all"

    # Admin permissions
    USERS_MANAGE = "users:manage"
    SYSTEM_MANAGE = "system:manage"


class Visibility(enum.StrEnum):
    """Resource visibility options for access control"""

    PUBLIC = "public"
    PRIVATE = "private"


class User(Base):
    __tablename__ = "users"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # User profile (currently synced from OAuth provider/ GitHub)
    username: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(512))

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    # Role is used for permissions
    role = mapped_column(
        str_enum(UserRole, "user_role"),
        default=UserRole.PENDING,
        nullable=False,
        index=True,
    )

    backends: Mapped[list["SnakedispatchBackend"]] = relationship(
        secondary=user_backends, back_populates="users"
    )

    def update_last_login(self) -> None:
        """Update last login timestamp to current time"""
        self.last_login = datetime.now(UTC)

    @property
    def permissions(self) -> list[str]:
        from pypsa_app.backend.permissions import get_user_permissions  # noqa: PLC0415

        return [p.value for p in get_user_permissions(self)]


class UserOAuthProvider(Base):
    """Links OAuth providers to users"""

    __tablename__ = "user_oauth_providers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50))
    provider_id: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now()
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_provider_provider_id"),
    )


class ApiKey(Base):
    """API key linked to a user for programmatic access (e.g. CI/CD)."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(8))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    owner: Mapped["User"] = relationship()
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)


class Network(Base):
    __tablename__ = "networks"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Ownership
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    owner: Mapped["User"] = relationship(foreign_keys=[user_id])

    # Provenance
    # link to the run that produced this network (if any)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.job_id", ondelete="SET NULL"),
        index=True,
    )
    source_run: Mapped["Run | None"] = relationship(foreign_keys=[source_run_id])

    # Visibility
    # public (all users) or private (owner only)
    visibility: Mapped[Visibility] = mapped_column(
        str_enum(Visibility, "visibility"),
        default=Visibility.PRIVATE,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now(), index=True
    )
    update_history: Mapped[list | None] = mapped_column(JSON, default=list)
    # File information
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(Text, unique=True, index=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    file_hash: Mapped[str | None] = mapped_column(String(64))

    # Metadata from PyPSA Network
    name: Mapped[str | None] = mapped_column(String(255))
    dimensions_count: Mapped[Any | None] = mapped_column(JSON)
    components_count: Mapped[Any | None] = mapped_column(JSON)
    meta: Mapped[Any | None] = mapped_column(JSON)
    facets: Mapped[Any | None] = mapped_column(JSON)
    topology_svg: Mapped[str | None] = mapped_column(Text)

    @property
    def tags(self) -> list | None:
        tags = self.meta.get("tags") if self.meta else None
        return tags if isinstance(tags, list) else None


class SavedView(Base):
    """A saved dashboard view configuration for a network."""

    __tablename__ = "saved_views"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    owner: Mapped["User"] = relationship(foreign_keys=[user_id])
    network_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("networks.id", ondelete="CASCADE"),
        index=True,
    )
    network: Mapped["Network | None"] = relationship(foreign_keys=[network_id])
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[Visibility] = mapped_column(
        str_enum(Visibility, "visibility"),
        default=Visibility.PRIVATE,
        nullable=False,
    )
    config: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )


class RunStatus(enum.StrEnum):
    """Run status, mirrors Snakedispatch's JobStatus."""

    PENDING = "PENDING"
    SETUP = "SETUP"
    RUNNING = "RUNNING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class Run(Base):
    """Persists run metadata for statistics.

    Job metadata is synced from Snakedispatch on every status poll
    and survives after Snakedispatch garbage collects the job.
    """

    __tablename__ = "runs"

    job_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    owner: Mapped["User"] = relationship(foreign_keys=[user_id])
    backend_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("snakedispatch_backends.id", ondelete="SET NULL"),
        index=True,
    )
    backend: Mapped["SnakedispatchBackend | None"] = relationship(
        foreign_keys=[backend_id]
    )
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, server_default=func.now()
    )

    # Job creation inputs (set once at creation, never synced)
    workflow: Mapped[str] = mapped_column(Text)
    configfile: Mapped[str | None] = mapped_column(String(512))
    snakemake_args: Mapped[Any | None] = mapped_column(JSON)
    extra_files: Mapped[Any | None] = mapped_column(JSON)
    cache: Mapped[Any | None] = mapped_column(JSON)

    callback_url: Mapped[str | None] = mapped_column(String(512))
    visibility: Mapped[Visibility] = mapped_column(
        str_enum(Visibility, "visibility"),
        default=Visibility.PRIVATE,
        nullable=False,
        index=True,
    )

    # Job metadata (synced from Snakedispatch)
    git_ref: Mapped[str | None] = mapped_column(String(255))
    git_sha: Mapped[str | None] = mapped_column(String(40))
    status = mapped_column(
        str_enum(RunStatus, "run_status"),
        default=RunStatus.PENDING,
        nullable=False,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    import_networks: Mapped[Any | None] = mapped_column(JSON)
    total_job_count: Mapped[int | None] = mapped_column(Integer)
    jobs_finished: Mapped[int | None] = mapped_column(Integer)

    networks: Mapped[list["Network"]] = relationship(
        foreign_keys="Network.source_run_id", viewonly=True
    )
