"""Network response schemas"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pypsa_app.backend.models import Visibility
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.common import PaginationMeta


class NetworkResponse(BaseModel):
    """Network API response"""

    id: UUID
    created_at: datetime
    update_history: list[Any] | None = None
    filename: str
    file_path: str
    file_size: int | None = None
    file_hash: str | None = None

    # PyPSA Network metadata
    name: str | None = None
    dimensions_count: dict[str, Any] | None = None
    components_count: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    facets: dict[str, Any] | None = None

    # Ownership, visibility and provenance
    visibility: Visibility = Visibility.PRIVATE
    owner: UserPublicResponse
    shared_with: list[UserPublicResponse] = []
    source_run_id: UUID | None = None

    # Model properties
    tags: list[str | dict] | None = None

    model_config = ConfigDict(from_attributes=True)


class NetworkListMeta(PaginationMeta):
    """Extended pagination meta with network-specific fields"""

    owners: list[UserPublicResponse] | None = None


class NetworkListResponse(BaseModel):
    data: list[NetworkResponse]
    meta: NetworkListMeta


class NetworkUpdate(BaseModel):
    """Fields any network owner can update"""

    visibility: Visibility | None = None
    name: str | None = None


class NetworkAdminUpdate(NetworkUpdate):
    """Admin-only fields"""

    user_id: UUID | None = None


class NetworkShareRequest(BaseModel):
    """Request to share a network with a user"""

    user_id: UUID


class NetworkShareResponse(BaseModel):
    """Response for network share status"""

    network_id: UUID
    shared_with: list[UserPublicResponse]
