"""SQLAlchemy database models"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    Column,
    Enum,
    ForeignKey,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from pypsa_app.backend.database import Base


class UuidType(TypeDecorator):
    """Store UUIDs efficiently. Native UUID in PostgreSQL and string in SQLite."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQL_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        uuid_value = value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        return uuid_value if dialect.name == "postgresql" else str(uuid_value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(value)


def str_enum(enum_cls, name):
    """Create SQLAlchemy Enum that stores enum values as native PostgreSQL enum."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


class UserRole(str, enum.Enum):
    """User roles for access control"""

    ADMIN = "admin"
    USER = "user"
    PENDING = "pending"


class Permission(str, enum.Enum):
    """Permission constants for access control. Format: resource:action"""

    # Network permissions
    NETWORKS_VIEW = "networks:view"
    NETWORKS_CREATE = "networks:create"  # Upload new networks
    NETWORKS_SCAN = "networks:scan"  # Scan file system for networks
    NETWORKS_UPDATE = "networks:update"
    NETWORKS_DELETE = "networks:delete"
    NETWORKS_VIEW_ALL = "networks:view_all"

    # User management permissions
    USERS_VIEW = "users:view"
    USERS_MANAGE = "users:manage"


class NetworkVisibility(str, enum.Enum):
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

    def update_last_login(self):
        """Update last login timestamp to current time"""
        self.last_login = datetime.now(timezone.utc)

    @property
    def permissions(self) -> list[str]:
        from pypsa_app.backend.permissions import get_user_permissions

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


class Network(Base):
    __tablename__ = "networks"

    # Primary key
    id = Column(UuidType(), primary_key=True, default=uuid.uuid4)

    # Ownership (nullable for system networks without an owner)
    user_id = Column(
        UuidType(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner = relationship("User", foreign_keys=[user_id])

    # Visibility: public (all users) or private (owner only)
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
