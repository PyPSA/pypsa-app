"""Celery tasks for long-running PyPSA operations"""

import logging
import os
import tempfile
import uuid as _uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from pypsa_app.backend.api.utils.network import (
    make_temp_path,
    stream_to_file_with_limit,
)
from pypsa_app.backend.cache import cache
from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.models import Run, RunStatus, SnakedispatchBackend
from pypsa_app.backend.schemas.task import TaskResultResponse
from pypsa_app.backend.services.callback import fire_callback_sync
from pypsa_app.backend.services.explore import get_explore as get_explore_service
from pypsa_app.backend.services.network import import_network_file
from pypsa_app.backend.services.run import SnakedispatchClient
from pypsa_app.backend.services.statistics import get_plot as get_plot_service
from pypsa_app.backend.services.statistics import (
    get_statistics as get_statistics_service,
)
from pypsa_app.backend.settings import settings
from pypsa_app.backend.task_queue import task_app
from pypsa_app.backend.utils.errors import sanitize_task_error
from pypsa_app.backend.utils.validation import validate_url_external

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
            # SQLite stores naive datetimes; strip tzinfo but always generate UTC
            generated_at=datetime.now(UTC).replace(tzinfo=None).isoformat(),
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
            status="error", task_id=self.request.id, error=sanitize_task_error(e)
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


@task_app.task(bind=True, name="tasks.get_explore")
def get_explore_task(self: Any, **kwargs: Any) -> dict[str, Any]:
    """Background task for explore map generation"""
    func = cache("explore", ttl=settings.plot_cache_ttl)(get_explore_service)
    return _execute_task(self, "Explore map generation", func, **kwargs)


def _import_tmp(
    *, tmp_path: str, original_filename: str, user_id: str
) -> dict[str, Any]:
    """Import a temp network file into storage and create the DB record."""
    tmp = Path(tmp_path)
    user_uuid = _uuid.UUID(user_id)
    db = SessionLocal()
    try:
        network = import_network_file(tmp, original_filename, user_uuid, db)
        db.commit()
        db.refresh(network)
        return {
            "network_id": str(network.id),
            "filename": network.filename,
            "size": network.file_size,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        tmp.unlink(missing_ok=True)
        db.close()


def _import_from_url(*, url: str, user_id: str) -> dict[str, Any]:
    url_path = PurePosixPath(httpx.URL(url).path)
    if url_path.suffix.lower() != ".nc":
        msg = "URL must point to a .nc file"
        raise ValueError(msg)

    validate_url_external(url)

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    tmp = make_temp_path(user_id)
    try:
        timeout = httpx.Timeout(connect=10, read=30, write=None, pool=5)
        with httpx.stream("GET", url, follow_redirects=False, timeout=timeout) as resp:
            if resp.is_redirect:
                msg = "URL returned a redirect. Provide a direct download link."
                raise ValueError(msg)  # noqa: TRY301
            resp.raise_for_status()
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                limit = settings.max_upload_size_mb
                msg = f"Remote file too large. Maximum: {limit} MB"
                raise ValueError(msg)  # noqa: TRY301
            stream_to_file_with_limit(resp.iter_bytes(), tmp, max_bytes)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return _import_tmp(
        tmp_path=str(tmp),
        original_filename=url_path.name or "network.nc",
        user_id=user_id,
    )


@task_app.task(bind=True, name="tasks.import_network_from_file")
def import_network_from_file_task(
    self: Any, *, tmp_path: str, original_filename: str, user_id: str
) -> dict[str, Any]:
    """Import a previously-uploaded network file and create the DB record."""
    return _execute_task(
        self,
        "Network import",
        _import_tmp,
        tmp_path=tmp_path,
        original_filename=original_filename,
        user_id=user_id,
    )


@task_app.task(bind=True, name="tasks.import_network_from_url")
def import_network_from_url_task(
    self: Any, *, url: str, user_id: str
) -> dict[str, Any]:
    """Download a network from ``url`` and import it."""
    return _execute_task(
        self,
        "Network import from URL",
        _import_from_url,
        url=url,
        user_id=user_id,
    )


@task_app.task(bind=True, name="tasks.import_run_outputs")
def import_run_outputs_task(self: Any, job_id: str) -> None:  # noqa: PLR0915
    """Download .nc outputs from a completed run and import as networks."""
    db = SessionLocal()
    try:
        run = db.get(Run, job_id)
        if not run or run.status != RunStatus.UPLOADING:
            return

        backend = db.get(SnakedispatchBackend, run.backend_id)
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
                run = db.get(Run, job_id)
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
            run = db.get(Run, job_id)
            if run:
                run.status = RunStatus.ERROR
                db.commit()
                fire_callback_sync(run)
        except Exception:
            logger.exception("Failed to mark run as ERROR", extra={"run_id": job_id})
    finally:
        db.close()
