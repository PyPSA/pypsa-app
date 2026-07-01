"""Background sync of non-terminal runs from Snakedispatch backends."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from sqlalchemy import select

from pypsa_app.backend.api.utils.task_utils import submit_flow
from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.flows import import_run_outputs_flow
from pypsa_app.backend.models import Run, RunStatus
from pypsa_app.backend.services.backend_registry import backend_registry
from pypsa_app.backend.services.callback import fire_callback_async
from pypsa_app.backend.services.run import SnakedispatchError

logger = logging.getLogger(__name__)

# Hold references to fire-and-forget callback tasks to prevent garbage collection.
_background_tasks: set[asyncio.Task] = set()

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

_CALLBACK_STATUSES = SYNCED_STATUSES - {RunStatus.UPLOADING}


def sync_run_from_job(run: Run, job: dict, db: Session) -> tuple[bool, bool]:
    """Update a Run record from a Snakedispatch response dict.

    Returns:
        (needs_callback, needs_import) — both booleans.
        needs_callback: True if a callback should be fired after the transaction
            commits.
        needs_import:   True if import_run_outputs should be submitted after commit.
    """
    old_status = run.status
    changed = False
    for field in _SYNC_FIELDS:
        new_val = job.get(field)
        if new_val is not None and getattr(run, field) != new_val:
            setattr(run, field, new_val)
            changed = True

    needs_import = False
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
            return False, True
        if completed_with_import_pending:
            run.status = RunStatus.COMPLETED
            changed = True
        elif new_status and run.status != new_status:
            run.status = new_status
            changed = True

    if changed:
        db.flush()

    needs_callback = (
        run.status in _CALLBACK_STATUSES and old_status not in _CALLBACK_STATUSES
    )
    return needs_callback, needs_import


def sync_non_terminal_runs() -> tuple[list[dict], list[str]]:
    """Poll all backends and update runs that haven't reached a terminal state.

    Returns:
        (callbacks, import_job_ids) where:
          callbacks      — list of {"url": ..., "payload": ...} dicts to fire async
          import_job_ids — list of job_id strings for which import flows must be
              submitted
    """
    callbacks: list[dict] = []
    import_job_ids: list[str] = []
    db = SessionLocal()
    try:
        non_terminal = db.scalars(
            select(Run).where(Run.status.notin_(SYNCED_STATUSES))
        ).all()
        if not non_terminal:
            return callbacks, import_job_ids

        for backend_id, client in backend_registry.all_clients().items():
            backend_runs = [r for r in non_terminal if r.backend_id == backend_id]
            if not backend_runs:
                continue
            callback_runs: list[Run] = []
            pending_imports: list[str] = []
            for run in backend_runs:
                try:
                    job = client.get_job(str(run.job_id))
                    needs_callback, needs_import = sync_run_from_job(run, job, db)
                    if needs_callback:
                        callback_runs.append(run)
                    if needs_import:
                        pending_imports.append(str(run.job_id))
                except SnakedispatchError as exc:
                    if exc.status_code == 404:  # noqa: PLR2004
                        logger.warning(
                            "Run %s not found on backend %s, marking as ERROR",
                            run.job_id,
                            backend_id,
                        )
                        run.status = RunStatus.ERROR
                        callback_runs.append(run)
                    else:
                        logger.warning(
                            "Transient error syncing run %s on backend %s: %s",
                            run.job_id,
                            backend_id,
                            exc.detail,
                        )
                except Exception:
                    logger.warning(
                        "Unexpected error syncing run %s on backend %s",
                        run.job_id,
                        backend_id,
                        exc_info=True,
                    )
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.warning(
                    "Sync commit failed for backend %s", backend_id, exc_info=True
                )
                continue
            callbacks.extend(
                {
                    "url": str(run.callback_url),
                    "payload": {
                        "run_id": str(run.job_id),
                        "status": run.status.value,
                    },
                }
                for run in callback_runs
                if run.callback_url
            )
            import_job_ids.extend(pending_imports)
    finally:
        db.close()
    return callbacks, import_job_ids


async def run_sync_loop(interval: float = 10.0) -> None:
    """Periodically sync non-terminal runs in a background thread."""
    while True:
        await asyncio.sleep(interval)
        try:
            callbacks, import_job_ids = await asyncio.to_thread(sync_non_terminal_runs)
            for cb in callbacks:
                t = asyncio.create_task(fire_callback_async(cb["url"], cb["payload"]))
                _background_tasks.add(t)
                t.add_done_callback(_background_tasks.discard)
            for job_id in import_job_ids:
                t = asyncio.create_task(
                    submit_flow(import_run_outputs_flow, job_id=job_id)
                )
                _background_tasks.add(t)
                t.add_done_callback(_background_tasks.discard)
        except Exception:
            logger.warning("Background run sync failed", exc_info=True)
