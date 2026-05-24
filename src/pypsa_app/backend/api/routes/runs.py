"""Workflow run routes."""

import logging
import re
import threading
import urllib.parse
import uuid
from pathlib import PurePosixPath
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import (
    Authorized,
    get_db,
    require_permission,
    require_run,
)
from pypsa_app.backend.api.pagination import (
    FilteredListParams,
    apply_pagination,
    list_meta,
)
from pypsa_app.backend.cache import cache
from pypsa_app.backend.filters import (
    FieldMap,
    FieldSpec,
    apply_filter_to_query,
    enum_coercer,
    name_to_id,
)
from pypsa_app.backend.models import (
    Permission,
    Run,
    RunStatus,
    SnakedispatchBackend,
    User,
    Visibility,
)
from pypsa_app.backend.permissions import has_permission
from pypsa_app.backend.schemas.backend import BackendPublicResponse
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.run import (
    OutputFileResponse,
    RunCreate,
    RunListResponse,
    RunResponse,
    RunSummary,
    RunUpdate,
)
from pypsa_app.backend.services.backend_registry import backend_registry
from pypsa_app.backend.services.callback import (
    _build_payload,
    post_callback_sync,
)
from pypsa_app.backend.services.run import SnakedispatchClient, SnakedispatchError
from pypsa_app.backend.services.sync import (
    SYNCED_STATUSES,
    sync_run_from_job,
)
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
        return db.scalars(
            select(SnakedispatchBackend)
            .where(SnakedispatchBackend.is_active.is_(True))
            .order_by(SnakedispatchBackend.name)
        ).all()
    return db.scalars(
        select(SnakedispatchBackend)
        .join(SnakedispatchBackend.users)
        .where(User.id == user.id, SnakedispatchBackend.is_active.is_(True))
        .order_by(SnakedispatchBackend.name)
    ).all()


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

    payload = body.model_dump(
        exclude_none=True,
        exclude={
            "backend_id",
            "import_networks",
            "cache",
            "callback_url",
            "visibility",
        },
    )
    if body.cache:
        payload["cache_key"] = body.cache.key
        payload["cache_dirs"] = body.cache.dirs
    result = client.submit_job(payload)
    try:
        job_id = uuid.UUID(str(result["job_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(502, "Snakedispatch returned an invalid job_id") from exc

    run = Run(
        job_id=job_id,
        user_id=user.id,
        backend_id=backend.id,
        workflow=result.get("workflow", body.workflow),
        configfile=result.get("configfile", body.configfile),
        snakemake_args=body.snakemake_args,
        extra_files=body.extra_files,
        cache=body.cache.model_dump() if body.cache else None,
        import_networks=body.import_networks,
        callback_url=str(body.callback_url) if body.callback_url else None,
        visibility=body.visibility,
        status=RunStatus(result.get("status", "PENDING")),
    )
    db.add(run)
    db.commit()
    db.refresh(run, ["owner", "backend", "networks"])

    logger.info(
        "Run created",
        extra={
            "run_id": str(job_id),
            "user": user.username,
            "backend": backend.name,
        },
    )

    return RunResponse.model_validate(run)


def _build_run_field_map(user: User, db: Session) -> FieldMap:
    # 'owner' accepts "me" (current user) or a username.
    username_to_id = name_to_id(db, User, "username", "user")
    return {
        "status": FieldSpec(Run.status, enum_coercer(RunStatus)),
        "workflow": FieldSpec(Run.workflow, str),
        "owner": FieldSpec(
            Run.user_id, lambda s: user.id if s == "me" else username_to_id(s)
        ),
        "git_ref": FieldSpec(Run.git_ref, str),
        "configfile": FieldSpec(Run.configfile, str),
        "backend": FieldSpec(
            Run.backend_id, name_to_id(db, SnakedispatchBackend, "name", "backend")
        ),
    }


@router.get("/", response_model=RunListResponse)
def list_runs(
    filters: FilteredListParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
) -> RunListResponse:
    """List runs visible to the current user."""
    is_admin = has_permission(user, Permission.RUNS_MANAGE_ALL)
    user_filter = (
        or_(
            Run.user_id == user.id,
            Run.visibility == Visibility.PUBLIC,
        )
        if not is_admin
        else None
    )

    # Collect distinct values per column for filter dropdowns
    def _distinct_vals(col: Any) -> list:
        stmt = select(col).where(col.isnot(None)).distinct()
        if user_filter is not None:
            stmt = stmt.where(user_filter)
        return sorted(db.scalars(stmt).all())

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
        db.scalars(
            select(SnakedispatchBackend)
            .where(SnakedispatchBackend.id.in_(backend_ids))
            .order_by(SnakedispatchBackend.name)
        ).all()
        if backend_ids
        else None
    )

    owner_ids = _distinct_vals(Run.user_id)
    filter_options["owners"] = (
        db.scalars(select(User).where(User.id.in_(owner_ids))).all()
        if owner_ids
        else None
    )

    query = select(Run).options(joinedload(Run.owner), joinedload(Run.backend))
    if user_filter is not None:
        query = query.where(user_filter)

    query = apply_filter_to_query(
        query,
        filters.filter_q,
        _build_run_field_map(user, db),
        text_fields=(Run.workflow, Run.configfile),
    )

    runs_query, total = apply_pagination(
        query,
        Run,
        filters,
        session=db,
        allowed_sort_fields={"created_at", "status", "workflow"},
    )
    runs = db.scalars(runs_query).all()

    return RunListResponse(
        data=[RunSummary.model_validate(r) for r in runs],
        meta={**list_meta(total, filters, len(runs)), **filter_options},
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    auth: Authorized[Run] = Depends(require_run("read")),
    db: Session = Depends(get_db),
) -> RunResponse:
    """Get run detail."""
    run = auth.model
    # Sync from Snakedispatch if not in terminal state
    if run.status not in SYNCED_STATUSES:
        client = backend_registry.get_client(run.backend_id)
        if client:
            try:
                job = client.get_job(str(run.job_id))
                needs_callback = sync_run_from_job(run, job, db)
                db.commit()
                if needs_callback and run.callback_url:
                    # TODO: replace with proper async callback or
                    # FastAPI BackgroundTasks.
                    url = str(run.callback_url)
                    payload = _build_payload(run)
                    threading.Thread(
                        target=post_callback_sync,
                        args=(url, payload),
                        daemon=True,
                    ).start()
            except SnakedispatchError:
                pass

    return RunResponse.model_validate(run)


@router.patch("/{run_id}", response_model=RunResponse)
def update_run(
    body: RunUpdate,
    auth: Authorized[Run] = Depends(require_run("modify")),
    db: Session = Depends(get_db),
) -> RunResponse:
    """Update run properties. Only owner or admin can update."""
    run = auth.model
    if body.visibility is not None:
        run.visibility = body.visibility
    db.commit()
    db.refresh(run)
    return RunResponse.model_validate(run)


@router.get("/{run_id}/logs")
def stream_run_logs(
    auth: Authorized[Run] = Depends(require_run("read")),
    format: Literal["text"] | None = Query(
        None, description="'text' for plain text logs"
    ),
) -> StreamingResponse:
    """Stream live logs via SSE, or plain text with ?format=text."""
    run = auth.model
    sd_client = _get_client_for_run(run)
    if format == "text":
        return StreamingResponse(
            sd_client.get_job_logs_text(str(run.job_id)),
            media_type="text/plain",
        )
    return StreamingResponse(
        sd_client.subscribe_job_logs(str(run.job_id)),
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
    auth: Authorized[Run] = Depends(require_run("read")),
) -> dict:
    """Get workflow metadata (DAG, rules, jobs, errors) for a run."""
    run = auth.model
    client = _get_client_for_run(run)
    return client.get_job_workflow(str(run.job_id))


@router.get("/{run_id}/outputs", response_model=list[OutputFileResponse])
def list_run_outputs(
    auth: Authorized[Run] = Depends(require_run("read")),
) -> list[dict]:
    """List output files for a completed run."""
    run = auth.model
    return _get_job_outputs_cached(str(run.job_id), str(run.backend_id))


@router.get("/{run_id}/outputs/{path:path}")
def download_run_output(
    path: str = PathParam(..., description="File path relative to work directory"),
    format: Literal["text"] | None = Query(
        None, description="'text' for inline plain text"
    ),
    auth: Authorized[Run] = Depends(require_run("read")),
) -> StreamingResponse:
    """Download an output file, or display inline with ?format=text."""
    run = auth.model
    if ".." in PurePosixPath(path).parts:
        raise HTTPException(400, "Invalid path")
    sd_client = _get_client_for_run(run)
    if format == "text":
        return StreamingResponse(
            sd_client.download_job_output(str(run.job_id), path),
            media_type="text/plain",
            headers={"Content-Disposition": "inline"},
        )
    filename = urllib.parse.quote(
        re.sub(r'[\x00-\x1f\x7f"\\;]', "_", path.rsplit("/", 1)[-1])
    )
    return StreamingResponse(
        sd_client.download_job_output(str(run.job_id), path),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/{run_id}/cancel", response_model=MessageResponse)
def cancel_run(
    auth: Authorized[Run] = Depends(require_run("modify")),
    db: Session = Depends(get_db),
) -> dict:
    """Cancel a running run. Keeps the record visible."""
    run = auth.model

    sd_client = _get_client_for_run(run)
    try:
        result = sd_client.cancel_job(str(run.job_id))
        needs_callback = sync_run_from_job(run, result, db)
        db.commit()
        if needs_callback and run.callback_url:
            # TODO: replace with proper async callback or
            # FastAPI BackgroundTasks.
            url = str(run.callback_url)
            payload = _build_payload(run)
            threading.Thread(
                target=post_callback_sync, args=(url, payload), daemon=True
            ).start()
    except SnakedispatchError as e:
        if e.status_code in (404, 409):
            if run.status not in SYNCED_STATUSES:
                run.status = RunStatus.CANCELLED
                db.commit()
                if run.callback_url:
                    # TODO: replace with proper async callback or
                    # FastAPI BackgroundTasks.
                    url = str(run.callback_url)
                    payload = _build_payload(run)
                    threading.Thread(
                        target=post_callback_sync,
                        args=(url, payload),
                        daemon=True,
                    ).start()
        else:
            raise

    logger.info(
        "Run cancelled",
        extra={
            "run_id": str(run.job_id),
            "user": auth.user.username,
        },
    )

    return {"message": "Run cancelled"}


@router.delete("/{run_id}", response_model=MessageResponse)
def remove_run(
    auth: Authorized[Run] = Depends(require_run("modify")),
    db: Session = Depends(get_db),
) -> dict:
    """Remove a run, cancel if still active, and delete the DB row."""
    run = auth.model

    # Try to clean up remotely but don't fail the request if it errors
    client = backend_registry.get_client(run.backend_id)
    if client:
        try:
            client.delete_job(str(run.job_id))
        except Exception:
            logger.warning(
                "Remote cleanup failed for run %s", run.job_id, exc_info=True
            )

    db.delete(run)
    db.commit()

    logger.info(
        "Run removed",
        extra={
            "run_id": str(run.job_id),
            "user": auth.user.username,
        },
    )

    return {"message": "Run removed"}
