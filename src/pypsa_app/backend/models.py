"""SQLAlchemy database models"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID
from sqlalchemy.sql import func

from pypsa_app.backend.database import Base


class UuidType(TypeDecorator):
    """Store UUIDs efficiently: native UUID in PostgreSQL (16 bytes), string in SQLite (36 bytes)"""

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


UUID_COLUMN = UuidType()


class UserRole(str, enum.Enum):
    """User roles for access control"""

    ADMIN = "admin"
    USER = "user"
    PENDING = "pending"


class User(Base):
    __tablename__ = "users"

    # Primary key
    id = Column(UUID_COLUMN, primary_key=True, default=uuid.uuid4)

    # User profile (synced from OAuth provider)
    username = Column(String(255), nullable=False, unique=True)
    email = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_login = Column(TIMESTAMP, nullable=True)

    # Role is used for permissions
    role = Column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=UserRole.PENDING,
        nullable=False,
        index=True,
    )

    def update_last_login(self):
        """Update last login timestamp to current time"""
        self.last_login = datetime.now(timezone.utc)

    @property
    def permissions(self) -> list[str]:
        mapping = {
            UserRole.ADMIN: [
                "admin",
                "view_networks",
                "create_networks",
                "delete_networks",
            ],
            UserRole.USER: ["view_networks", "create_networks", "delete_networks"],
            UserRole.PENDING: [],
        }
        return mapping.get(self.role, [])


class UserOAuthProvider(Base):
    """Links OAuth providers to users"""

    __tablename__ = "user_oauth_providers"

    id = Column(UUID_COLUMN, primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID_COLUMN,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)
    provider_id = Column(String(255), nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_provider_provider_id"),
    )


class Network(Base):
    __tablename__ = "networks"

    # Primary key
    id = Column(UUID_COLUMN, primary_key=True, default=uuid.uuid4)

    # Ownership (nullable for backwards compatibility with existing networks)
    user_id = Column(
        UUID_COLUMN,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_public = Column(Boolean, default=False, nullable=False)

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
        if self.meta and "tags" in self.meta and isinstance(self.meta["tags"], list):
            return self.meta["tags"]
        return None
