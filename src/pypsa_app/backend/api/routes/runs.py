"""Workflow run routes."""

import logging
import re
import urllib.parse
import uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.models import Permission, Run, RunStatus, User
from pypsa_app.backend.permissions import can_access_run, can_modify_run, has_permission
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.run import (
    RunCreate,
    RunListResponse,
    RunResponse,
)
from pypsa_app.backend.services.run import SmkExecutorClient, SmkExecutorError
from pypsa_app.backend.settings import settings
from pypsa_app.backend.tasks import import_run_outputs_task

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses where the remote executor is done — no need to sync from smk-executor.
SMK_SYNCED_STATUSES = {
    RunStatus.UPLOADING,
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.ERROR,
    RunStatus.CANCELLED,
}


def _get_smk_client() -> SmkExecutorClient:
    """Return SmkExecutorClient or raise 503 if not configured."""
    if not settings.smk_executor_url:
        raise HTTPException(503, "Run service is not configured")
    return SmkExecutorClient(settings.smk_executor_url)


def _check_run_or_404(run_id: uuid.UUID, db: Session, user: User) -> Run:
    """Load run record with access check."""
    run = (
        db.query(Run)
        .options(joinedload(Run.owner))
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
    """Update a Run record from a smk-executor response dict."""
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


@router.post("/", response_model=RunResponse, status_code=201)
def create_run(
    body: RunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_MODIFY)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> RunResponse:
    """Submit a new run."""
    payload = body.model_dump(exclude_none=True)
    result = smk_client.submit_job(payload)

    run = Run(
        job_id=result["job_id"],
        user_id=user.id,
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
    db.refresh(run)

    logger.info(
        "Run created",
        extra={
            "run_id": result["job_id"],
            "user": user.username,
        },
    )

    return RunResponse.model_validate(run)


@router.get("/", response_model=RunListResponse)
def list_runs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> RunListResponse:
    """List runs visible to the current user."""
    query = db.query(Run).options(joinedload(Run.owner))
    if not has_permission(user, Permission.RUNS_MANAGE_ALL):
        query = query.filter(Run.user_id == user.id)

    total = query.count()
    runs = query.order_by(Run.created_at.desc()).offset(skip).limit(limit).all()

    # Sync non-terminal runs in this page from smk-executor
    non_terminal = [r for r in runs if r.status not in SMK_SYNCED_STATUSES]
    if non_terminal:
        try:
            all_jobs = smk_client.list_jobs()
            jobs_by_id = {j["job_id"]: j for j in all_jobs}

            for run in non_terminal:
                job = jobs_by_id.get(str(run.job_id))
                if job:
                    _sync_run_from_job(run, job, db)

            db.commit()
        except SmkExecutorError:
            # smk-executor unreachable, serve from DB only
            pass

    return RunListResponse(
        data=[RunResponse.model_validate(r) for r in runs],
        meta={"total": total, "skip": skip, "limit": limit, "count": len(runs)},
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> RunResponse:
    """Get run detail."""
    run = _check_run_or_404(run_id, db, user)

    # Sync from smk-executor if not in terminal state
    if run.status not in SMK_SYNCED_STATUSES:
        try:
            job = smk_client.get_job(str(run_id))
            _sync_run_from_job(run, job, db)
            db.commit()
        except SmkExecutorError:
            # smk-executor unreachable or job already garbage
            # collected, fall back to local DB
            pass

    return RunResponse.model_validate(run)


@router.get("/{run_id}/logs")
def stream_run_logs(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    format: str | None = Query(None, description="'text' for plain text logs"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> StreamingResponse:
    """Stream live logs via SSE, or plain text with ?format=text."""
    _check_run_or_404(run_id, db, user)
    if format == "text":
        return StreamingResponse(
            smk_client.get_job_logs_text(str(run_id)),
            media_type="text/plain",
        )
    return StreamingResponse(
        smk_client.subscribe_job_logs(str(run_id)),
        media_type="text/event-stream",
    )


@router.get("/{run_id}/outputs")
def list_run_outputs(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> list[dict]:
    """List output files for a completed run."""
    _check_run_or_404(run_id, db, user)
    return smk_client.get_job_outputs(str(run_id))


@router.get("/{run_id}/outputs/{path:path}")
def download_run_output(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    path: str = PathParam(..., description="File path relative to work directory"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> StreamingResponse:
    """Download an output file."""
    if ".." in PurePosixPath(path).parts:
        raise HTTPException(400, "Invalid path")
    _check_run_or_404(run_id, db, user)
    filename = urllib.parse.quote(
        re.sub(r'[\x00-\x1f\x7f"\\;]', "_", path.rsplit("/", 1)[-1])
    )
    return StreamingResponse(
        smk_client.download_job_output(str(run_id), path),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/{run_id}/cancel", response_model=MessageResponse)
def cancel_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_MODIFY)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> dict:
    """Cancel a running run. Keeps the record visible."""
    run = _check_run_or_404(run_id, db, user)
    if not can_modify_run(user, run):
        raise HTTPException(403, "You don't have permission to cancel this run")

    try:
        result = smk_client.cancel_job(str(run_id))
        _sync_run_from_job(run, result, db)
        db.commit()
    except SmkExecutorError as e:
        if e.status_code in (404, 409):
            if run.status not in SMK_SYNCED_STATUSES:
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
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> dict:
    """Remove a run, cancel if still active, and delete the DB row."""
    run = _check_run_or_404(run_id, db, user)
    if not can_modify_run(user, run):
        raise HTTPException(403, "You don't have permission to remove this run")

    db.delete(run)
    db.commit()

    # Try to clean up remotely but don't fail the request if it errors
    try:
        smk_client.delete_job(str(run_id))
    except Exception:
        logger.warning("Remote cleanup failed for run %s", run_id, exc_info=True)

    logger.info(
        "Run removed",
        extra={
            "run_id": str(run_id),
            "user": user.username,
        },
    )

    return {"message": "Run removed"}
