from pydantic import BaseModel, Field, field_validator

from pypsa_app.backend.schemas.statistics import StatisticsRequest
from pypsa_app.backend.utils.allowlists import ALLOWED_CHART_TYPES


class PlotRequest(StatisticsRequest):
    """Request schema for plot generation (extends StatisticsRequest with plot_type)"""

    plot_type: str = Field(..., description="Plot method (e.g., 'bar', 'area', 'line')")

    @field_validator("plot_type")
    @classmethod
    def validate_plot_type(cls, v: str) -> str:
        if v not in ALLOWED_CHART_TYPES:
            msg = f"Invalid plot_type '{v}'. Allowed: {sorted(ALLOWED_CHART_TYPES)}"
            raise ValueError(msg)
        return v


class ExploreRequest(BaseModel):
    """Request schema for interactive map via n.plot.explore()"""

    _ALLOWED_BRANCH_COMPONENTS: frozenset[str] = frozenset(
        {"Line", "Link", "Transformer"}
    )

    network_id: str = Field(..., description="Network UUID")
    branch_components: list[str] | None = Field(
        default=None, description="Branch types to display (Line, Link, Transformer)"
    )
    geometry: bool = Field(
        default=False, description="Use line geometries instead of straight lines"
    )

    @field_validator("branch_components")
    @classmethod
    def validate_branch_components(
        cls,
        v: list[str] | None,
    ) -> list[str] | None:
        if v is None:
            return v
        invalid = set(v) - cls._ALLOWED_BRANCH_COMPONENTS
        if invalid:
            allowed = sorted(cls._ALLOWED_BRANCH_COMPONENTS)
            msg = f"Invalid branch_components {sorted(invalid)}. Allowed: {allowed}"
            raise ValueError(msg)
        return v
