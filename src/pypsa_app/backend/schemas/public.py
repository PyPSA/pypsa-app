"""Public (unauthenticated) response schemas"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pypsa_app.backend.models import RunStatus, Visibility
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.backend import BackendPublicResponse
from pypsa_app.backend.schemas.run import RunNetworkSummary


class PublicRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(validation_alias="job_id")
    status: RunStatus
    workflow: str
    configfile: str | None = None
    git_ref: str | None = None
    git_sha: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_job_count: int | None = None
    jobs_finished: int | None = None
    visibility: Visibility
    owner: UserPublicResponse
    backend: BackendPublicResponse
    networks: list[RunNetworkSummary]
