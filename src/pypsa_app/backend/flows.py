"""Prefect flows for long-running PyPSA operations."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid as _uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import httpx
from sqlalchemy.exc import SQLAlchemyError

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
from pypsa_app.backend.utils.errors import sanitize_task_error
from pypsa_app.backend.utils.validation import validate_url_external

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_flow_run_id() -> str:
    from prefect.context import get_run_context  # noqa: PLC0415

    return str(get_run_context().flow_run.id)


def _execute_flow(name: str, func: Callable, **kwargs: Any) -> dict[str, Any]:
    """Run func and return a structured result dict.

    User-facing errors (ValueError, httpx.HTTPStatusError) are caught and
    returned as a result with status="error" so the client can display them.
    Infrastructure errors (DB, OS, unexpected) are re-raised so Prefect's retry
    mechanism can handle them.
    """
    task_id = _current_flow_run_id()
    try:
        data = func(**kwargs)
        return TaskResultResponse(
            status="success",
            task_id=task_id,
            generated_at=datetime.now(UTC).replace(tzinfo=None).isoformat(),
            data=data,
            request=kwargs,
        ).model_dump()
    except (ValueError, httpx.HTTPStatusError) as e:
        logger.exception(
            "%s failed",
            name,
            extra={
                "task_id": task_id,
                "error": str(e),
                "error_type": type(e).__name__,
                **kwargs,
            },
        )
        return TaskResultResponse(
            status="error",
            task_id=task_id,
            error=sanitize_task_error(e),
        ).model_dump()
    except (SQLAlchemyError, OSError):
        logger.exception(
            "%s failed with infrastructure error",
            name,
            extra={"task_id": task_id, **kwargs},
        )
        raise


# ---------------------------------------------------------------------------
# Analytics flows
# ---------------------------------------------------------------------------

# TODO: reconsider the dual-layer caching approach here (needs discussion).
# Currently Redis caches the raw computation result inside the flow, and
# Prefect persists the TaskResultResponse to the filesystem per flow run.
# Two alternatives worth evaluating:
#   1. Replace Redis with Prefect's built-in result caching (cache_key_fn +
#      cache_expiration on the @flow). Prefect would skip re-running the flow
#      entirely for identical parameters and return the persisted result
#      directly, removing the Redis dependency for analytics flows. The
#      trade-off: a flow run is still created and registered with the Prefect
#      server on every submission — it just resolves instantly on a cache hit.
#      The async polling contract (submit → flow_run_id → poll) stays intact.
#   2. Keep Redis but check it before submitting a flow at all (e.g. in
#      queue_task or the route handler). A cache hit would avoid the overhead
#      of creating a flow run entirely. However, this breaks the current async
#      polling contract — the client expects a flow_run_id to poll against, but
#      if no flow is submitted there is no flow_run_id. This would require
#      either returning the result synchronously on cache hits (different API
#      contract) or generating a synthetic task ID and storing the result under
#      it separately, which adds significant complexity. Needs careful thought.


def _get_statistics_impl(**kwargs: Any) -> dict[str, Any]:
    func = cache("statistics", ttl=settings.plot_cache_ttl)(get_statistics_service)
    return _execute_flow("Statistics generation", func, **kwargs)


def _get_plot_impl(**kwargs: Any) -> dict[str, Any]:
    func = cache("plot", ttl=settings.plot_cache_ttl)(get_plot_service)
    return _execute_flow("Plot generation", func, **kwargs)


def _get_explore_impl(**kwargs: Any) -> dict[str, Any]:
    func = cache("explore", ttl=settings.plot_cache_ttl)(get_explore_service)
    return _execute_flow("Explore map generation", func, **kwargs)


# ---------------------------------------------------------------------------
# Network import helpers (shared between file and URL import flows)
# ---------------------------------------------------------------------------


def _import_tmp(
    *, tmp_path: str, original_filename: str, user_id: str
) -> dict[str, Any]:
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


def _import_network_from_file_impl(
    *, tmp_path: str, original_filename: str, user_id: str
) -> dict[str, Any]:
    return _execute_flow(
        "Network import",
        _import_tmp,
        tmp_path=tmp_path,
        original_filename=original_filename,
        user_id=user_id,
    )


def _import_network_from_url_impl(*, url: str, user_id: str) -> dict[str, Any]:
    return _execute_flow(
        "Network import from URL",
        _import_from_url,
        url=url,
        user_id=user_id,
    )


# ---------------------------------------------------------------------------
# Run output import (fire-and-forget, no polling)
# ---------------------------------------------------------------------------


def _import_run_outputs_impl(job_id: str) -> None:  # noqa: PLR0915
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
                    source_path=output_path,
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


# ---------------------------------------------------------------------------
# Prefect @flow wrappers
# ---------------------------------------------------------------------------

from prefect import flow  # noqa: E402

# TODO: migrate result storage from local filesystem to S3 object storage for
# distributed deployments where the worker and API are on separate machines.


@flow(name="get-statistics", timeout_seconds=7200, retries=1, persist_result=True)
def get_statistics_flow(
    file_paths: list[str], statistic: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    return _get_statistics_impl(
        file_paths=file_paths, statistic=statistic, parameters=parameters
    )


@flow(name="get-plot", timeout_seconds=7200, retries=1, persist_result=True)
def get_plot_flow(
    file_paths: list[str],
    statistic: str,
    plot_type: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _get_plot_impl(
        file_paths=file_paths,
        statistic=statistic,
        plot_type=plot_type,
        parameters=parameters,
    )


@flow(name="get-explore", timeout_seconds=7200, retries=1, persist_result=True)
def get_explore_flow(
    file_paths: list[str], parameters: dict[str, Any]
) -> dict[str, Any]:
    return _get_explore_impl(file_paths=file_paths, parameters=parameters)


@flow(
    name="import-network-from-file",
    timeout_seconds=7200,
    persist_result=True,
)
def import_network_from_file_flow(
    *, tmp_path: str, original_filename: str, user_id: str
) -> dict[str, Any]:
    return _import_network_from_file_impl(
        tmp_path=tmp_path,
        original_filename=original_filename,
        user_id=user_id,
    )


@flow(
    name="import-network-from-url", timeout_seconds=7200, retries=1, persist_result=True
)
def import_network_from_url_flow(*, url: str, user_id: str) -> dict[str, Any]:
    return _import_network_from_url_impl(url=url, user_id=user_id)


@flow(name="import-run-outputs", timeout_seconds=7200, retries=1)
def import_run_outputs_flow(job_id: str) -> None:
    _import_run_outputs_impl(job_id)
