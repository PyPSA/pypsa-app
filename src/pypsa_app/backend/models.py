"""SQLAlchemy database models"""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeEngine

from pypsa_app.backend.database import Base


class UuidType(TypeDecorator):
    """Store UUIDs efficiently. Native UUID in PostgreSQL and string in SQLite."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQL_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        uuid_value = value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        return uuid_value if dialect.name == "postgresql" else str(uuid_value)

    def process_result_value(self, value: Any, dialect: Dialect) -> uuid.UUID | None:
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(value)


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
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "backend_id",
        UuidType(),
        ForeignKey("snakedispatch_backends.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SnakedispatchBackend(Base):
    """A registered Snakedispatch execution backend."""

    __tablename__ = "snakedispatch_backends"

    id = Column(UuidType(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    url = Column(String(512), nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    users = relationship("User", secondary=user_backends, back_populates="backends")


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


class NetworkVisibility(enum.StrEnum):
    """Network visibility options for access control"""

    PUBLIC = "public"
    PRIVATE = "private"


class User(Base):
    __tablename__ = "users"

    # Primary key
    id = Column(UuidType(), primary_key=True, default=uuid.uuid4)

    # User profile (currently synced from OAuth provider/ GitHub)
    username = Column(String(255), nullable=False, unique=True)
    email = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_login = Column(TIMESTAMP, nullable=True)

    # Role is used for permissions
    role = Column(
        str_enum(UserRole, "user_role"),
        default=UserRole.PENDING,
        nullable=False,
        index=True,
    )

    backends = relationship(
        "SnakedispatchBackend", secondary=user_backends, back_populates="users"
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

    id = Column(UuidType(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)
    provider_id = Column(String(255), nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_provider_provider_id"),
    )


class ApiKey(Base):
    """API key linked to a user for programmatic access (e.g. CI/CD)."""

    __tablename__ = "api_keys"

    id = Column(UuidType(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    key_prefix = Column(String(8), nullable=False)
    user_id = Column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner = relationship("User")
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_used_at = Column(TIMESTAMP, nullable=True)
    expires_at = Column(TIMESTAMP, nullable=True)


class Network(Base):
    __tablename__ = "networks"

    # Primary key
    id = Column(UuidType(), primary_key=True, default=uuid.uuid4)

    # Ownership
    user_id = Column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner = relationship("User", foreign_keys=[user_id])

    # Provenance
    # link to the run that produced this network (if any)
    source_run_id = Column(
        UuidType(),
        ForeignKey("runs.job_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_run = relationship("Run", foreign_keys=[source_run_id])

    # Visibility
    # public (all users) or private (owner only)
    visibility = Column(
        str_enum(NetworkVisibility, "network_visibility"),
        default=NetworkVisibility.PRIVATE,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    update_history = Column(JSON, default=list)
    # File information
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False, unique=True, index=True)
    file_size = Column(BigInteger)
    file_hash = Column(String(64))  # SHA256 for change detection

    # Metadata from PyPSA Network
    name = Column(String(255))
    dimensions_count = Column(JSON)
    components_count = Column(JSON)
    meta = Column(JSON)
    facets = Column(JSON)
    topology_svg = Column(Text)

    @property
    def tags(self) -> list | None:
        tags = self.meta.get("tags") if self.meta else None
        return tags if isinstance(tags, list) else None


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

    job_id = Column(UuidType(), primary_key=True)
    user_id = Column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner = relationship("User", foreign_keys=[user_id])
    backend_id = Column(
        UuidType(),
        ForeignKey("snakedispatch_backends.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    backend = relationship("SnakedispatchBackend", foreign_keys=[backend_id])
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Job creation inputs (set once at creation, never synced)
    workflow = Column(Text, nullable=False)
    configfile = Column(String(512), nullable=True)
    snakemake_args = Column(JSON, nullable=True)
    extra_files = Column(JSON, nullable=True)
    cache = Column(JSON, nullable=True)

    # Job metadata (synced from Snakedispatch)
    git_ref = Column(String(255), nullable=True)
    git_sha = Column(String(40), nullable=True)
    status = Column(
        str_enum(RunStatus, "run_status"),
        default=RunStatus.PENDING,
        nullable=False,
    )
    exit_code = Column(Integer, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    import_networks = Column(JSON, nullable=True)
    total_job_count = Column(Integer, nullable=True)
    jobs_finished = Column(Integer, nullable=True)

    networks = relationship(
        "Network", foreign_keys="Network.source_run_id", viewonly=True
    )
