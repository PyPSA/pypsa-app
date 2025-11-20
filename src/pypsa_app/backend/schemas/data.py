from pydantic import BaseModel, Field, field_validator


class DataRequest(BaseModel):
    """Request for component data with pagination"""

    network_id: str = Field(..., description="Network UUID")
    component: str = Field(
        ..., description="Component name (e.g., 'generators', 'buses')"
    )
    offset: int = Field(default=0, ge=0, description="Number of rows to skip")
    limit: int = Field(
        default=100, ge=1, le=10000, description="Maximum number of rows to return"
    )

    @field_validator("network_id")
    @classmethod
    def validate_network_id(cls, v):
        if not v:
            raise ValueError("Network ID is required")
        return v

    @field_validator("component")
    @classmethod
    def validate_component(cls, v):
        if not v:
            raise ValueError("Component name is required")
        return v
