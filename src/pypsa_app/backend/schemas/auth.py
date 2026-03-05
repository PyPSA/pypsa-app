"""Authentication response schemas"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from pypsa_app.backend.models import UserRole
from pypsa_app.backend.schemas.common import PaginationMeta


class UserPublicResponse(BaseModel):
    """Minimal public user info for embedding in other responses"""

    id: UUID
    username: str
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class UserResponse(UserPublicResponse):
    """Full user information response"""

    email: str | None = None
    created_at: datetime
    last_login: datetime | None = None
    permissions: list[str]


class UserListResponse(BaseModel):
    """Paginated list of users"""

    data: list[UserResponse]
    meta: PaginationMeta


class UserRoleUpdate(BaseModel):
    """Request body for role update"""

    role: UserRole


class UserCreate(BaseModel):
    """Request body for creating a user"""

    username: str = Field(..., min_length=1, max_length=255)
    role: UserRole
