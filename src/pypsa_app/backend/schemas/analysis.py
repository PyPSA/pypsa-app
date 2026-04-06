"""Request/response schemas for custom analysis endpoints."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from pypsa_app.backend.utils.allowlists import ALLOWED_ANALYSIS_TYPES


class AnalysisRequest(BaseModel):
    """Request for custom analysis (dispatch, line loading, prices, etc.)"""

    network_ids: list[str] = Field(..., description="List of network UUIDs")
    analysis_type: str = Field(
        ...,
        description="Analysis type (e.g., 'dispatch_area')",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Analysis-specific parameters (country, resample, top_n, etc.)",
    )

    @field_validator("network_ids")
    @classmethod
    def validate_network_ids(cls, v: list[str]) -> list[str]:
        if not v:
            msg = "At least one network ID is required"
            raise ValueError(msg)
        return v

    @field_validator("analysis_type")
    @classmethod
    def validate_analysis_type(cls, v: str) -> str:
        if v not in ALLOWED_ANALYSIS_TYPES:
            msg = (
                f"Invalid analysis_type '{v}'. "
                f"Allowed: {sorted(ALLOWED_ANALYSIS_TYPES)}"
            )
            raise ValueError(msg)
        return v
