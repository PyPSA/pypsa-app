"""Run response schemas"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pypsa_app.backend.models import RunStatus
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.common import PaginationMeta


class RunCache(BaseModel):
    """Cache configuration for a run."""

    key: str
    dirs: list[str]


class OutputFileResponse(BaseModel):
    """Single output file entry."""

    path: str
    size: int


class RunCreate(BaseModel):
    """POST /runs request body."""

    workflow: str
    configfile: str | None = None
    snakemake_args: list[str] | None = None
    extra_files: dict[str, str] | None = None
    cache: RunCache | None = None
    import_networks: list[str] | None = None


class RunResponse(BaseModel):
    """Single run returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(validation_alias="job_id")
    workflow: str
    configfile: str | None = None
    snakemake_args: list[str] | None = None
    extra_files: dict[str, str] | None = None
    cache: RunCache | None = None
    import_networks: list[str] | None = None
    git_ref: str | None = None
    git_sha: str | None = None
    status: RunStatus
    exit_code: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    owner: UserPublicResponse


class RunListResponse(BaseModel):
    data: list[RunResponse]
    meta: PaginationMeta
