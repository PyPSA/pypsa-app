from typing import Any

from pydantic import BaseModel, Field, field_validator

from pypsa_app.backend.utils.allowlists import ALLOWED_STATISTICS


class StatisticsParams(BaseModel):
    """Request for statistics data

    For single network: Maps to Network.statistics.<statistic>(<parameters>)
    For multiple networks:
        Maps to NetworkCollection.statistics.<statistic>(<parameters>)
    """

    network_ids: list[str] = Field(
        ..., description="List of network UUIDs (single or multiple)"
    )
    statistic: str = Field(..., description="Statistics method to call")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the statistics method"
    )

    @field_validator("network_ids")
    @classmethod
    def validate_network_ids(cls, v: list[str]) -> list[str]:
        if not v:
            msg = "At least one network ID is required"
            raise ValueError(msg)
        return v

    @field_validator("statistic")
    @classmethod
    def validate_statistic(cls, v: str) -> str:
        if v not in ALLOWED_STATISTICS:
            msg = f"Invalid statistic '{v}'. Allowed: {sorted(ALLOWED_STATISTICS)}"
            raise ValueError(msg)
        return v
