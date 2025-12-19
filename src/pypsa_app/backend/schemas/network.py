"""Network response schemas"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, computed_field

from pypsa_app.backend.schemas.common import PaginationMeta


class NetworkSchema(BaseModel):
    """Pydantic schema for Network model"""

    id: UUID
    created_at: datetime
    update_history: list[Any] | None = None
    filename: str
    file_path: str
    file_size: int | None = None
    file_hash: str | None = None
    name: str | None = None
    dimensions_count: dict[str, Any] | None = None
    components_count: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    facets: dict[str, Any] | None = None
    topology_svg: str | None = None

    @computed_field
    @property
    def tags(self) -> list[str] | None:
        """Extract tags from meta field"""
        if self.meta and "tags" in self.meta and isinstance(self.meta["tags"], list):
            return self.meta["tags"]
        return None

    model_config = {"from_attributes": True}


class NetworkListResponse(BaseModel):
    data: list[NetworkSchema]
    meta: PaginationMeta
