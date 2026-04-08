"""Celery tasks for long-running PyPSA operations"""

import logging
import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pypsa_app.backend.cache import cache
from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.models import Run, RunStatus, SnakedispatchBackend
from pypsa_app.backend.schemas.task import TaskResultResponse
from pypsa_app.backend.services.analysis import run_analysis as run_analysis_service
from pypsa_app.backend.services.callback import fire_callback_sync
from pypsa_app.backend.services.network import import_network_file
from pypsa_app.backend.services.run import SnakedispatchClient
from pypsa_app.backend.services.statistics import get_plot as get_plot_service
from pypsa_app.backend.services.statistics import (
    get_statistics as get_statistics_service,
)
from pypsa_app.backend.settings import settings
from pypsa_app.backend.task_queue import task_app

logger = logging.getLogger(__name__)


def _execute_task(
    self: Any, name: str, func: Callable, **kwargs: Any
) -> dict[str, Any]:
    """Execute task with progress tracking, error handling, and result formatting"""
    self.update_state(state="PROGRESS", meta={"status": f"{name} in progress"})
    try:
        data = func(**kwargs)
        return TaskResultResponse(
            status="success",
            task_id=self.request.id,
            generated_at=datetime.now(UTC).isoformat(),
            data=data,
            request=kwargs,
        ).model_dump()
    except Exception as e:
        logger.exception(
            "%s failed",
            name,
            extra={
                "task_id": self.request.id,
                "error": str(e),
                "error_type": type(e).__name__,
                **kwargs,
            },
        )
        return TaskResultResponse(
            status="error", task_id=self.request.id, error=str(e)
        ).model_dump()


@task_app.task(bind=True, name="tasks.get_statistics")
def get_statistics_task(self: Any, **kwargs: Any) -> dict[str, Any]:
    """Background task for statistics generation"""
    func = cache("statistics", ttl=settings.plot_cache_ttl)(get_statistics_service)
    return _execute_task(self, "Statistics generation", func, **kwargs)


@task_app.task(bind=True, name="tasks.get_plot")
def get_plot_task(self: Any, **kwargs: Any) -> dict[str, Any]:
    """Background task for plot generation"""
    func = cache("plot", ttl=settings.plot_cache_ttl)(get_plot_service)
    return _execute_task(self, "Plot generation", func, **kwargs)


@task_app.task(bind=True, name="tasks.run_analysis")
def run_analysis_task(self: Any, **kwargs: Any) -> dict[str, Any]:
    """Background task for custom analysis generation"""
    func = cache("analysis", ttl=settings.plot_cache_ttl)(run_analysis_service)
    return _execute_task(self, "Analysis generation", func, **kwargs)


@task_app.task(bind=True, name="tasks.import_run_outputs")
def import_run_outputs_task(self: Any, job_id: str) -> None:  # noqa: PLR0915
    """Download .nc outputs from a completed run and import as networks."""
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.job_id == job_id).first()
        if not run or run.status != RunStatus.UPLOADING:
            return

        backend = (
            db.query(SnakedispatchBackend)
            .filter(SnakedispatchBackend.id == run.backend_id)
            .first()
        )
        if backend is None:
            logger.error(
                "Backend %s not found in DB for run %s",
                run.backend_id,
                job_id,
            )
            run.status = RunStatus.ERROR
            db.commit()
            fire_callback_sync(run)
            return
        sd_client = SnakedispatchClient(backend.url)
        wanted_set = set(run.import_networks or [])

        outputs = sd_client.get_job_outputs(job_id)
        nc_outputs = [
            o
            for o in outputs
            if str(o.get("path", "")).endswith(".nc")
            and str(o.get("path", "")) in wanted_set
        ]

        # If any import fails, rollback undoes all and run is marked ERROR.
        for output in nc_outputs:
            output_path = output["path"]
            fd, tmp_str = tempfile.mkstemp(suffix=".nc")
            os.close(fd)
            tmp = Path(tmp_str)
            try:
                sd_client.download_job_output_to_file(job_id, output_path, tmp)
                filename = PurePosixPath(output_path).name
                network = import_network_file(
                    tmp,
                    filename,
                    run.user_id,
                    db,
                    source_run_id=run.job_id,
                    visibility=run.visibility,
                )
                logger.info(
                    "Imported network from run output",
                    extra={
                        "run_id": job_id,
                        "output_path": output_path,
                        "network_id": str(network.id),
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to import run output",
                    extra={"run_id": job_id, "output_path": output_path},
                )
                db.rollback()
                run = db.query(Run).filter(Run.job_id == job_id).first()
                if run:
                    run.status = RunStatus.ERROR
                    db.commit()
                    fire_callback_sync(run)
                return
            finally:
                tmp.unlink(missing_ok=True)

        run.status = RunStatus.COMPLETED
        db.commit()
        fire_callback_sync(run)
    except Exception:
        logger.exception("Import task failed", extra={"run_id": job_id})
        try:
            run = db.query(Run).filter(Run.job_id == job_id).first()
            if run:
                run.status = RunStatus.ERROR
                db.commit()
                fire_callback_sync(run)
        except Exception:
            logger.exception("Failed to mark run as ERROR", extra={"run_id": job_id})
    finally:
        db.close()
