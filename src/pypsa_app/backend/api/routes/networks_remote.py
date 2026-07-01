"""Network import routes (upload, from-url)."""

import asyncio
from collections.abc import Iterator
from pathlib import PurePosixPath

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile

from pypsa_app.backend.api.deps import require_permission
from pypsa_app.backend.api.utils.network import (
    make_temp_path,
    stream_to_file_with_limit,
)
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.flows import (
    import_network_from_file_flow,
    import_network_from_url_flow,
)
from pypsa_app.backend.models import Permission, User
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.settings import settings
from pypsa_app.backend.utils.validation import ExternalHttpUrl

router = APIRouter()


def _iter_upload_file(file: UploadFile, chunk_size: int = 8192) -> Iterator[bytes]:
    while chunk := file.file.read(chunk_size):
        yield chunk


@router.post("/", response_model=TaskQueuedResponse, status_code=202)
async def upload_network(
    file: UploadFile,
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> dict:
    """Accept a .nc upload and enqueue import as a background task."""
    if not file.filename or not file.filename.endswith(".nc"):
        raise HTTPException(400, "Only .nc (NetCDF) files are accepted")

    safe_filename = PurePosixPath(file.filename).name
    if not safe_filename or not safe_filename.endswith(".nc"):
        raise HTTPException(400, "Invalid filename")
    safe_filename = safe_filename[:255]

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    tmp = make_temp_path(user.id)
    try:
        await asyncio.to_thread(
            stream_to_file_with_limit, _iter_upload_file(file), tmp, max_bytes
        )
    except ValueError as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(413, str(exc)) from exc
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    try:
        return await queue_task(
            import_network_from_file_flow,
            tmp_path=str(tmp),
            original_filename=safe_filename,
            user_id=str(user.id),
        )
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


@router.post("/from-url", response_model=TaskQueuedResponse, status_code=202)
async def create_network_from_url(
    url: ExternalHttpUrl = Body(..., embed=True),
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> dict:
    """Enqueue a task to download ``url`` and import it as a network."""
    url_str = str(url)
    if url.scheme not in {"http", "https"}:
        raise HTTPException(400, "URL must use http or https")
    if not url_str.lower().endswith(".nc"):
        raise HTTPException(400, "URL must point to a .nc file")

    return await queue_task(
        import_network_from_url_flow,
        url=url_str,
        user_id=str(user.id),
    )
