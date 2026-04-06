"""Schemas for saved dashboard views."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pypsa_app.backend.models import Visibility
from pypsa_app.backend.schemas.auth import UserPublicResponse


class ViewConfig(BaseModel):
    """Configuration for a saved view."""

    # Active tab/plot
    active_tab: str | None = None
    statistic: str | None = None
    plot_type: str | None = None

    # Filters
    selected_carriers: list[str] = []
    selected_countries: list[str] = []
    individual_plots: bool = False

    # Analysis settings
    analysis_type: str | None = None
    analysis_parameters: dict[str, Any] = {}

    # Component browser state
    selected_component: str | None = None
    component_columns: list[str] | None = None

    # Compare mode
    compare_network_ids: list[str] = []

    # Custom parameters
    extra: dict[str, Any] = {}


class SavedViewCreate(BaseModel):
    """Request to create a saved view."""

    name: str
    description: str | None = None
    network_id: UUID | None = None
    visibility: Visibility = Visibility.PRIVATE
    config: ViewConfig


class SavedViewUpdate(BaseModel):
    """Request to update a saved view."""

    name: str | None = None
    description: str | None = None
    visibility: Visibility | None = None
    config: ViewConfig | None = None


class SavedViewResponse(BaseModel):
    """Response for a saved view."""

    id: UUID
    name: str
    description: str | None = None
    network_id: UUID | None = None
    visibility: Visibility
    config: dict[str, Any]
    owner: UserPublicResponse
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SavedViewListResponse(BaseModel):
    """Paginated list of saved views."""

    data: list[SavedViewResponse]
    total: int
