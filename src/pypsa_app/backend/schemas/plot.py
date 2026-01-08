from pydantic import Field, field_validator

from pypsa_app.backend.schemas.statistics import StatisticsRequest
from pypsa_app.backend.utils.allowlists import ALLOWED_CHART_TYPES


class PlotRequest(StatisticsRequest):
    """Request schema for plot generation (extends StatisticsRequest with plot_type)"""

    plot_type: str = Field(..., description="Plot method (e.g., 'bar', 'area', 'line')")

    @field_validator("plot_type")
    @classmethod
    def validate_plot_type(cls, v):
        if v not in ALLOWED_CHART_TYPES:
            raise ValueError(
                f"Invalid plot_type '{v}'. Allowed: {sorted(ALLOWED_CHART_TYPES)}"
            )
        return v
