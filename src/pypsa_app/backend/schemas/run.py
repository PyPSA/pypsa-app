"""Run response schemas"""

import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from pypsa_app.backend.models import RunStatus, Visibility
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.backend import BackendPublicResponse
from pypsa_app.backend.schemas.common import ListMeta
from pypsa_app.backend.settings import settings


class RunCache(BaseModel):
    """Cache configuration for a run."""

    key: str = Field(
        ...,
        description=(
            "Cache identifier. Runs sharing a key reuse each other's "
            "cached directories."
        ),
    )
    dirs: list[str] = Field(
        ...,
        description="Directories to cache (e.g. `./data`).",
    )


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
    source_path: str | None = None


class RunCreate(BaseModel):
    """POST /runs request body."""

    workflow: str = Field(
        ...,
        description="Git URL of the Snakemake workflow repository to clone and run.",
    )
    git_ref: str | None = Field(
        default=None,
        description=(
            "Git branch, tag, or commit SHA to check out. "
            "Defaults to the repository's default branch."
        ),
    )
    configfile: str | None = Field(
        default=None,
        description="Path to a Snakemake config file in the workflow repo.",
    )
    snakemake_args: list[str] | None = Field(
        default=None,
        description=(
            "Additional snakemake arguments appended to the backend's execution "
            "defaults. No need to pass own execution defaults like `--cores` or "
            "`--profile`."
        ),
    )
    extra_files: dict[str, str] | None = Field(
        default=None,
        description=(
            "Files written into the working directory before execution. "
            "Keys are repo-relative paths, values are file contents."
        ),
    )
    env_vars: dict[str, str] | None = Field(
        default=None,
        description=(
            "Environment variables set before execution. "
            "Keys are variable names, values are their contents."
        ),
    )
    cache: RunCache | None = Field(
        default=None,
        description=(
            "Optional cache. Restores `dirs` from a previous run with the same `key` "
            "before launch, saves them back on success."
        ),
    )
    import_networks: list[str] | None = Field(
        default=None,
        description=(
            "Paths of `.nc` output files to import as networks after the run completes."
        ),
    )
    backend_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Snakedispatch backend that executes this run. "
            "Required when more than one backend is active."
        ),
    )
    visibility: Visibility = Field(
        default=Visibility.PRIVATE,
        description=(
            "Who can see this run. Public runs are visible to all logged-in users. "
            "Private runs only to you."
        ),
    )
    callback_url: HttpUrl | None = Field(
        default=None,
        description=(
            "Webhook invoked when the run finishes. "
            "Host must match the allowed callback domains setting."
        ),
    )

    @field_validator("callback_url")
    @classmethod
    def _validate_callback_domain(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is None:
            return v
        allowed = settings.resolved_callback_domains
        if not allowed:
            msg = "Callbacks are not enabled on this server"
            raise ValueError(msg)
        host = v.host or ""
        if not any(host == d or host.endswith(f".{d}") for d in allowed):
            msg = f"callback_url host '{host}' is not in the allowed domains"
            raise ValueError(msg)
        return v


class RunSummary(BaseModel):
    """Lightweight run representation for list endpoints."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(validation_alias="job_id")
    status: RunStatus
    owner: UserPublicResponse
    visibility: Visibility = Visibility.PRIVATE
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
    callback_url: str | None = None
    networks: list[RunNetworkSummary] = []

    @field_validator("callback_url", mode="before")
    @classmethod
    def _redact_callback_url(cls, v: str | None) -> str | None:
        if not v:
            return None
        parsed = urlparse(v)
        return f"{parsed.scheme}://{parsed.hostname}/***"


class RunListMeta(ListMeta):
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


class RunUpdate(BaseModel):
    visibility: Visibility | None = None


class RunAdminUpdate(RunUpdate):
    user_id: uuid.UUID | None = None
