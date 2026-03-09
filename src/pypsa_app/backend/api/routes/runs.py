"""Workflow run routes."""

import logging
import re
import urllib.parse
import uuid
from collections import defaultdict
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse
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
from pypsa_app.backend.settings import settings
from pypsa_app.backend.tasks import import_run_outputs_task

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses where the remote executor is done — no need to sync from Snakedispatch.
SYNCED_STATUSES = {
    RunStatus.UPLOADING,
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.ERROR,
    RunStatus.CANCELLED,
}


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


# Statuses that should not be resynced or trigger import again
_IMPORT_DONE_STATUSES = {RunStatus.UPLOADING, RunStatus.COMPLETED, RunStatus.ERROR}


def _sync_run_from_job(run: Run, job: dict, db: Session) -> None:
    """Update a Run record from a Snakedispatch response dict."""
    changed = False
    field_map = {
        "workflow": "workflow",
        "configfile": "configfile",
        "git_ref": "git_ref",
        "git_sha": "git_sha",
        "exit_code": "exit_code",
        "started_at": "started_at",
        "completed_at": "completed_at",
    }
    for db_field, job_key in field_map.items():
        new_val = job.get(job_key)
        if new_val is not None and getattr(run, db_field) != new_val:
            setattr(run, db_field, new_val)
            changed = True

    # Status needs enum conversion
    raw_status = job.get("status")
    if raw_status:
        try:
            new_status = RunStatus(raw_status)
        except ValueError:
            new_status = None

        completed_with_import_pending = (
            new_status == RunStatus.COMPLETED
            and run.status not in _IMPORT_DONE_STATUSES
        )
        if completed_with_import_pending and run.import_networks:
            run.status = RunStatus.UPLOADING
            changed = True
            db.flush()
            import_run_outputs_task.apply_async(args=(str(run.job_id),))
        elif completed_with_import_pending:
            # Nothing to import
            run.status = RunStatus.COMPLETED
            changed = True
        elif new_status and run.status != new_status:
            run.status = new_status
            changed = True

    if changed:
        db.flush()


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


@router.get("/", response_model=RunListResponse)
def list_runs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> RunListResponse:
    """List runs visible to the current user."""
    query = db.query(Run).options(joinedload(Run.owner), joinedload(Run.backend))
    if not has_permission(user, Permission.RUNS_MANAGE_ALL):
        query = query.filter(Run.user_id == user.id)

    total = query.count()
    runs = query.order_by(Run.created_at.desc()).offset(skip).limit(limit).all()

    # One sync call per backend to avoid redundant API requests
    non_terminal = [r for r in runs if r.status not in SYNCED_STATUSES]
    if non_terminal:
        by_backend: dict[uuid.UUID, list[Run]] = defaultdict(list)
        for r in non_terminal:
            by_backend[r.backend_id].append(r)

        for backend_id, backend_runs in by_backend.items():
            client = backend_registry.get_client(backend_id)
            if client is None:
                continue
            try:
                all_jobs = client.list_jobs()
                jobs_by_id = {j["job_id"]: j for j in all_jobs}
                for run in backend_runs:
                    job = jobs_by_id.get(str(run.job_id))
                    if job:
                        _sync_run_from_job(run, job, db)
                db.commit()
            except SnakedispatchError:
                pass

    return RunListResponse(
        data=[RunSummary.model_validate(r) for r in runs],
        meta={"total": total, "skip": skip, "limit": limit, "count": len(runs)},
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
                _sync_run_from_job(run, job, db)
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
        _sync_run_from_job(run, result, db)
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
