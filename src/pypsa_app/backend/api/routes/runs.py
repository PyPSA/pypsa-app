"""Workflow run routes."""

import logging
import re
import urllib.parse
import uuid
from pathlib import PurePosixPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.cache import cache
from pypsa_app.backend.models import (
    Permission,
    Run,
    RunStatus,
    SnakedispatchBackend,
    User,
)
from pypsa_app.backend.permissions import can_access_run, can_modify_run, has_permission
from pypsa_app.backend.schemas.backend import BackendPublicResponse
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.run import (
    OutputFileResponse,
    RunCreate,
    RunListResponse,
    RunResponse,
    RunSummary,
)
from pypsa_app.backend.services.backend_registry import backend_registry
from pypsa_app.backend.services.run import SnakedispatchClient, SnakedispatchError
from pypsa_app.backend.services.sync import SYNCED_STATUSES, sync_run_from_job
from pypsa_app.backend.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_client_for_run(run: Run) -> SnakedispatchClient:
    """Resolve a SnakedispatchClient from the run's backend_id."""
    client = backend_registry.get_client(run.backend_id)
    if client is None:
        raise HTTPException(503, "Run backend is not available")
    return client


def _get_user_backends(user: User, db: Session) -> list[SnakedispatchBackend]:
    """Return active backends available to the user.

    Users with RUNS_MANAGE_ALL get all active backends, bypassing the assignment table.
    """
    if has_permission(user, Permission.RUNS_MANAGE_ALL):
        return (
            db.query(SnakedispatchBackend)
            .filter(SnakedispatchBackend.is_active.is_(True))
            .order_by(SnakedispatchBackend.name)
            .all()
        )
    return (
        db.query(SnakedispatchBackend)
        .join(SnakedispatchBackend.users)
        .filter(User.id == user.id, SnakedispatchBackend.is_active.is_(True))
        .order_by(SnakedispatchBackend.name)
        .all()
    )


def _check_run(run_id: uuid.UUID, db: Session, user: User) -> Run:
    """Load run record with access check."""
    run = (
        db.query(Run)
        .options(
            joinedload(Run.owner), joinedload(Run.backend), joinedload(Run.networks)
        )
        .filter(Run.job_id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(404, "Run not found")
    if not can_access_run(user, run):
        raise HTTPException(404, "Run not found")
    return run


@router.get("/backends", response_model=list[BackendPublicResponse])
def list_user_backends(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> list[SnakedispatchBackend]:
    """Return the backends available to the current user."""
    return _get_user_backends(user, db)


@router.post("/", response_model=RunResponse, status_code=201)
def create_run(
    body: RunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_MODIFY)),
) -> RunResponse:
    """Submit a new run."""
    available = _get_user_backends(user, db)
    if not available:
        raise HTTPException(503, "No execution backends available")

    if body.backend_id is not None:
        backend = next((b for b in available if b.id == body.backend_id), None)
        if backend is None:
            raise HTTPException(403, "You don't have access to the requested backend")
    elif len(available) == 1:
        backend = available[0]
    else:
        raise HTTPException(
            400,
            "backend_id is required when multiple backends are available",
        )

    client = backend_registry.get_client(backend.id)
    if client is None:
        raise HTTPException(503, "Backend is not available")

    payload = body.model_dump(exclude_none=True, exclude={"backend_id"})
    result = client.submit_job(payload)

    run = Run(
        job_id=result["job_id"],
        user_id=user.id,
        backend_id=backend.id,
        workflow=result.get("workflow", body.workflow),
        configfile=result.get("configfile", body.configfile),
        snakemake_args=body.snakemake_args,
        extra_files=body.extra_files,
        cache=body.cache.model_dump() if body.cache else None,
        import_networks=body.import_networks,
        status=RunStatus(result.get("status", "PENDING")),
    )
    db.add(run)
    db.commit()
    db.refresh(run, ["owner", "backend", "networks"])

    logger.info(
        "Run created",
        extra={
            "run_id": result["job_id"],
            "user": user.username,
            "backend": backend.name,
        },
    )

    return RunResponse.model_validate(run)


class RunListFilters(BaseModel):
    """Query parameters for filtering the runs list."""

    skip: int = 0
    limit: int = 100
    statuses: list[str] | None = Query(None, description="Filter by status values")
    workflows: list[str] | None = Query(None, description="Filter by workflow names")
    owners: list[str] | None = Query(
        None, description="Filter by owner IDs. Use 'me' for current user."
    )
    git_refs: list[str] | None = Query(None, description="Filter by git ref")
    configfiles: list[str] | None = Query(None, description="Filter by configfile")
    backends: list[str] | None = Query(
        None, description="Filter by backend IDs (UUIDs)"
    )


@router.get("/", response_model=RunListResponse)
def list_runs(
    filters: RunListFilters = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> RunListResponse:
    """List runs visible to the current user."""
    is_admin = has_permission(user, Permission.RUNS_MANAGE_ALL)
    user_filter = Run.user_id == user.id if not is_admin else None

    # Collect distinct values per column for filter dropdowns
    def _distinct_vals(col: Any) -> list:
        q = db.query(col).filter(col.isnot(None))
        if user_filter is not None:
            q = q.filter(user_filter)
        return sorted(r[0] for r in q.distinct().all())

    all_statuses = list(RunStatus)
    present_statuses = set(_distinct_vals(Run.status))
    filter_options: dict[str, Any] = {
        "statuses": [s for s in all_statuses if s in present_statuses],
        "workflows": _distinct_vals(Run.workflow),
        "git_refs": _distinct_vals(Run.git_ref),
        "configfiles": _distinct_vals(Run.configfile),
    }

    backend_ids = _distinct_vals(Run.backend_id)
    filter_options["backends"] = (
        db.query(SnakedispatchBackend)
        .filter(SnakedispatchBackend.id.in_(backend_ids))
        .order_by(SnakedispatchBackend.name)
        .all()
        if backend_ids
        else None
    )

    if is_admin:
        owner_ids = _distinct_vals(Run.user_id)
        filter_options["owners"] = (
            db.query(User).filter(User.id.in_(owner_ids)).all() if owner_ids else None
        )
    else:
        filter_options["owners"] = None

    query = db.query(Run).options(joinedload(Run.owner), joinedload(Run.backend))
    if user_filter is not None:
        query = query.filter(user_filter)
    if filters.statuses:
        try:
            parsed_statuses = [RunStatus(s) for s in filters.statuses]
        except ValueError as e:
            raise HTTPException(422, f"Invalid status filter: {e}") from None
        query = query.filter(Run.status.in_(parsed_statuses))
    if filters.workflows:
        query = query.filter(Run.workflow.in_(filters.workflows))
    if filters.owners:
        resolved_ids = [user.id if o == "me" else o for o in filters.owners]
        query = query.filter(Run.user_id.in_(resolved_ids))
    if filters.git_refs:
        query = query.filter(Run.git_ref.in_(filters.git_refs))
    if filters.configfiles:
        query = query.filter(Run.configfile.in_(filters.configfiles))
    if filters.backends:
        try:
            parsed_backends = [uuid.UUID(b) for b in filters.backends]
        except ValueError as e:
            raise HTTPException(422, f"Invalid backend ID: {e}") from None
        query = query.filter(Run.backend_id.in_(parsed_backends))

    total = query.count()
    runs = (
        query.order_by(Run.created_at.desc())
        .offset(filters.skip)
        .limit(filters.limit)
        .all()
    )

    return RunListResponse(
        data=[RunSummary.model_validate(r) for r in runs],
        meta={
            "total": total,
            "skip": filters.skip,
            "limit": filters.limit,
            "count": len(runs),
            **filter_options,
        },
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> RunResponse:
    """Get run detail."""
    run = _check_run(run_id, db, user)

    # Sync from Snakedispatch if not in terminal state
    if run.status not in SYNCED_STATUSES:
        client = backend_registry.get_client(run.backend_id)
        if client:
            try:
                job = client.get_job(str(run_id))
                sync_run_from_job(run, job, db)
                db.commit()
            except SnakedispatchError:
                pass

    return RunResponse.model_validate(run)


@router.get("/{run_id}/logs")
def stream_run_logs(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    format: str | None = Query(None, description="'text' for plain text logs"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> StreamingResponse:
    """Stream live logs via SSE, or plain text with ?format=text."""
    run = _check_run(run_id, db, user)
    sd_client = _get_client_for_run(run)
    if format == "text":
        return StreamingResponse(
            sd_client.get_job_logs_text(str(run_id)),
            media_type="text/plain",
        )
    return StreamingResponse(
        sd_client.subscribe_job_logs(str(run_id)),
        media_type="text/event-stream",
    )


@cache("run_outputs", ttl=settings.run_outputs_cache_ttl)
def _get_job_outputs_cached(job_id: str, backend_id: str) -> list[dict]:
    """Fetch job outputs via Snakedispatch (cached at module level)."""
    client = backend_registry.get_client(uuid.UUID(backend_id))
    if client is None:
        return []
    return client.get_job_outputs(job_id)


@router.get("/{run_id}/workflow")
def get_run_workflow(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> dict:
    """Get workflow metadata (DAG, rules, jobs, errors) for a run."""
    run = _check_run(run_id, db, user)
    client = _get_client_for_run(run)
    return client.get_job_workflow(str(run_id))


@router.get("/{run_id}/outputs", response_model=list[OutputFileResponse])
def list_run_outputs(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> list[dict]:
    """List output files for a completed run."""
    run = _check_run(run_id, db, user)
    return _get_job_outputs_cached(str(run_id), str(run.backend_id))


@router.get("/{run_id}/outputs/{path:path}")
def download_run_output(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    path: str = PathParam(..., description="File path relative to work directory"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> StreamingResponse:
    """Download an output file."""
    if ".." in PurePosixPath(path).parts:
        raise HTTPException(400, "Invalid path")
    run = _check_run(run_id, db, user)
    sd_client = _get_client_for_run(run)
    filename = urllib.parse.quote(
        re.sub(r'[\x00-\x1f\x7f"\\;]', "_", path.rsplit("/", 1)[-1])
    )
    return StreamingResponse(
        sd_client.download_job_output(str(run_id), path),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/{run_id}/cancel", response_model=MessageResponse)
def cancel_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_MODIFY)),
) -> dict:
    """Cancel a running run. Keeps the record visible."""
    run = _check_run(run_id, db, user)
    if not can_modify_run(user, run):
        raise HTTPException(403, "You don't have permission to cancel this run")

    sd_client = _get_client_for_run(run)
    try:
        result = sd_client.cancel_job(str(run_id))
        sync_run_from_job(run, result, db)
        db.commit()
    except SnakedispatchError as e:
        if e.status_code in (404, 409):
            if run.status not in SYNCED_STATUSES:
                run.status = RunStatus.CANCELLED
                db.commit()
        else:
            raise

    logger.info(
        "Run cancelled",
        extra={
            "run_id": str(run_id),
            "user": user.username,
        },
    )

    return {"message": "Run cancelled"}


@router.delete("/{run_id}", response_model=MessageResponse)
def remove_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_MODIFY)),
) -> dict:
    """Remove a run, cancel if still active, and delete the DB row."""
    run = _check_run(run_id, db, user)
    if not can_modify_run(user, run):
        raise HTTPException(403, "You don't have permission to remove this run")

    # Try to clean up remotely but don't fail the request if it errors
    client = backend_registry.get_client(run.backend_id)
    if client:
        try:
            client.delete_job(str(run_id))
        except Exception:
            logger.warning("Remote cleanup failed for run %s", run_id, exc_info=True)

    db.delete(run)
    db.commit()

    logger.info(
        "Run removed",
        extra={
            "run_id": str(run_id),
            "user": user.username,
        },
    )

    return {"message": "Run removed"}
