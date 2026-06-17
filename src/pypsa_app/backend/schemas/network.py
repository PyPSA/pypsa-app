"""Network response schemas"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from pypsa_app.backend.models import Visibility
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.common import ListMeta


class DimensionInfo(BaseModel):
    count: int
    start: datetime | None = None
    end: datetime | None = None
    freq: str | None = None


class DimensionsInfo(BaseModel):
    timesteps: DimensionInfo
    periods: DimensionInfo
    scenarios: DimensionInfo


class NetworkResponse(BaseModel):
    """Network API response"""

    id: UUID
    created_at: datetime
    update_history: list[Any] | None = None
    filename: str
    file_size: int | None = None
    file_hash: str | None = None
    file_path: str | None = None
    file_missing: bool = False

    # PyPSA Network metadata
    name: str | None = None
    dimensions: DimensionsInfo | None = None
    components_count: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    facets: dict[str, Any] | None = None

    # Ownership, visibility and provenance
    visibility: Visibility = Visibility.PRIVATE
    owner: UserPublicResponse
    source_run_id: UUID | None = None

    # Model properties
    tags: list[str | dict] | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _hide_internal_file_path(self) -> "NetworkResponse":
        self.file_path = None
        return self


class NetworkListMeta(ListMeta):
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


class ReportCard(BaseModel):
    id: str
    type: str
    x: int
    y: int
    w: int
    h: int
    model_config = ConfigDict(extra="allow")


class ReportSchema(BaseModel):
    id: str
    name: str
    cards: list[ReportCard]
    isDefault: bool = False


class ReportsPayload(BaseModel):
    reports: list[ReportSchema]
    activeReportId: str


class ComponentDataResponse(BaseModel):
    component: str
    columns: list[str]
    dtypes: dict[str, str]
    index: list[str]
    data: list[list[Any]]
    total: int
    offset: int
    limit: int
