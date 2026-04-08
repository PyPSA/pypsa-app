"""Schemas for network component data browsing and editing."""

from typing import Any

from pydantic import BaseModel


class ComponentSummary(BaseModel):
    """Summary of a single network component type."""

    name: str
    list_name: str
    count: int
    category: str | None = None
    attrs: list[str] = []
    has_dynamic: bool = False
    dynamic_attrs: list[str] = []


class ComponentListResponse(BaseModel):
    """List of all components in a network."""

    components: list[ComponentSummary]
    total_components: int


class ComponentDataResponse(BaseModel):
    """Paginated component data (DataFrame rows)."""

    component: str
    columns: list[str]
    index: list[str]
    data: list[list[Any]]
    dtypes: dict[str, str]
    total: int
    skip: int
    limit: int


class ComponentTimeseriesResponse(BaseModel):
    """Time-varying data for a component attribute."""

    component: str
    attr: str
    columns: list[str]
    index: list[str]
    data: list[list[Any]]
    total_snapshots: int
    skip: int
    limit: int


class ComponentUpdateRequest(BaseModel):
    """Request to update component rows."""

    updates: dict[str, dict[str, Any]]
    """Mapping of index (component name) -> {column: new_value}"""
