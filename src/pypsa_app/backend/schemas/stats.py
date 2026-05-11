"""Statistics response schemas"""

from datetime import datetime

from pydantic import BaseModel


class UserStatsResponse(BaseModel):
    """Aggregated activity stats for a single user."""

    networks_count: int
    runs_total: int
    runs_by_status: dict[str, int]
    runs_by_backend: dict[str, int]
    total_storage_bytes: int
    last_activity: datetime | None
