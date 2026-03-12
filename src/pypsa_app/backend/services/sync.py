"""Background sync of non-terminal runs from Snakedispatch backends."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.models import Run, RunStatus
from pypsa_app.backend.services.backend_registry import backend_registry
from pypsa_app.backend.tasks import import_run_outputs_task

logger = logging.getLogger(__name__)

# Statuses where the remote executor is done, no need to sync from Snakedispatch
SYNCED_STATUSES = {
    RunStatus.UPLOADING,
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.ERROR,
    RunStatus.CANCELLED,
}

# Statuses where import has already been triggered or finished
_IMPORT_TRIGGERED_STATUSES = {RunStatus.UPLOADING, RunStatus.COMPLETED, RunStatus.ERROR}

_SYNC_FIELDS = [
    "workflow",
    "configfile",
    "git_ref",
    "git_sha",
    "exit_code",
    "started_at",
    "completed_at",
    "total_job_count",
    "jobs_finished",
]


def sync_run_from_job(run: Run, job: dict, db: Session) -> None:
    """Update a Run record from a Snakedispatch response dict."""
    changed = False
    for field in _SYNC_FIELDS:
        new_val = job.get(field)
        if new_val is not None and getattr(run, field) != new_val:
            setattr(run, field, new_val)
            changed = True

    raw_status = job.get("status")
    if raw_status:
        try:
            new_status = RunStatus(raw_status)
        except ValueError:
            new_status = None

        completed_with_import_pending = (
            new_status == RunStatus.COMPLETED
            and run.status not in _IMPORT_TRIGGERED_STATUSES
        )
        if completed_with_import_pending and run.import_networks:
            run.status = RunStatus.UPLOADING
            db.flush()
            import_run_outputs_task.apply_async(args=(str(run.job_id),))
            return
        if completed_with_import_pending:
            run.status = RunStatus.COMPLETED
            changed = True
        elif new_status and run.status != new_status:
            run.status = new_status
            changed = True

    if changed:
        db.flush()


def sync_non_terminal_runs() -> None:
    """Poll all backends and update runs that haven't reached a terminal state."""
    db = SessionLocal()
    try:
        non_terminal = db.query(Run).filter(Run.status.notin_(SYNCED_STATUSES)).all()
        if not non_terminal:
            return

        for backend_id, client in backend_registry.all_clients().items():
            backend_runs = [r for r in non_terminal if r.backend_id == backend_id]
            if not backend_runs:
                continue
            try:
                jobs_by_id = {j["job_id"]: j for j in client.list_jobs()}
                for run in backend_runs:
                    job = jobs_by_id.get(str(run.job_id))
                    if job:
                        sync_run_from_job(run, job, db)
                db.commit()
            except Exception:
                db.rollback()
                logger.warning("Sync failed for backend %s", backend_id, exc_info=True)
    finally:
        db.close()


async def run_sync_loop(interval: float = 10.0) -> None:
    """Periodically sync non-terminal runs in a background thread."""
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(sync_non_terminal_runs)
        except Exception:
            logger.warning("Background run sync failed", exc_info=True)
