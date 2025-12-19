"""Authentication response schemas"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from pypsa_app.backend.schemas.common import PaginationMeta


class UserResponse(BaseModel):
    """User information response"""

    id: UUID
    username: str
    email: str | None
    avatar_url: str | None
    created_at: datetime
    last_login: datetime | None
    permissions: list[str]

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated list of users"""

    data: list[UserResponse]
    meta: PaginationMeta


class UserRoleUpdate(BaseModel):
    """Request body for role update"""

    role: Literal["admin", "user", "pending"]
