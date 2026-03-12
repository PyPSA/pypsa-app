"""Run response schemas"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pypsa_app.backend.models import RunStatus
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.backend import BackendPublicResponse
from pypsa_app.backend.schemas.common import PaginationMeta


class RunCache(BaseModel):
    """Cache configuration for a run."""

    key: str
    dirs: list[str]


class OutputFileResponse(BaseModel):
    """Single output file entry."""

    path: str
    size: int


class RunNetworkSummary(BaseModel):
    """Lightweight summary of a network imported by a run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None = None
    filename: str


class RunCreate(BaseModel):
    """POST /runs request body."""

    workflow: str
    configfile: str | None = None
    snakemake_args: list[str] | None = None
    extra_files: dict[str, str] | None = None
    cache: RunCache | None = None
    import_networks: list[str] | None = None
    backend_id: uuid.UUID | None = None


class RunSummary(BaseModel):
    """Lightweight run representation for list endpoints."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(validation_alias="job_id")
    status: RunStatus
    owner: UserPublicResponse
    backend: BackendPublicResponse
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    workflow: str
    configfile: str | None = None
    git_ref: str | None = None
    git_sha: str | None = None
    total_job_count: int | None = None
    jobs_finished: int | None = None


class RunResponse(RunSummary):
    """Full run detail returned by the API."""

    snakemake_args: list[str] | None = None
    extra_files: dict[str, str] | None = None
    cache: RunCache | None = None
    import_networks: list[str] | None = None
    exit_code: int | None = None
    networks: list[RunNetworkSummary] = []


class RunListMeta(PaginationMeta):
    """Extended pagination meta with run-specific filter options."""

    statuses: list[str] | None = None
    workflows: list[str] | None = None
    owners: list[UserPublicResponse] | None = None
    git_refs: list[str] | None = None
    configfiles: list[str] | None = None
    backends: list[BackendPublicResponse] | None = None


class RunListResponse(BaseModel):
    data: list[RunSummary]
    meta: RunListMeta
