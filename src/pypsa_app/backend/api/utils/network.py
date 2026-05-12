"""Network utilities"""

from __future__ import annotations

import logging
import uuid as _uuid
from pathlib import Path
from typing import TYPE_CHECKING

from pypsa_app.backend.settings import settings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Session

    from pypsa_app.backend.models import Network

logger = logging.getLogger(__name__)


def delete_network(network: Network, db: Session, remove_file: bool = False) -> str:
    """Delete network from DB and (optionally) file system. Returns status message."""
    filename = network.filename
    file_path = Path(network.file_path)
    is_external = network.is_external

    db.delete(network)
    db.commit()

    # External files are not owned by the app, so keep them in place by default.
    if is_external and not remove_file:
        return f"Network {filename} removed (file kept in place)"

    if file_path.exists():
        try:
            file_path.unlink()
        except (PermissionError, OSError) as e:
            logger.warning("DB deleted but file remains for %s: %s", filename, e)
        else:
            logger.info("Deleted network file: %s", file_path)
            return f"Network {filename} deleted successfully"

    return f"Network {filename} removed from database (file cleanup may be needed)"


def make_temp_path(user_id: _uuid.UUID | str) -> Path:
    """Allocate a user-scoped temp path for an incoming network file."""
    user_dir = settings.networks_path / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / f"_upload_{_uuid.uuid4().hex}.tmp"


def stream_to_file_with_limit(
    chunks: Iterable[bytes], dest: Path, max_bytes: int
) -> int:
    """Stream chunks to file, raise `ValueError` if `max_bytes` exceeded."""
    bytes_written = 0
    with dest.open("wb") as f:
        for chunk in chunks:
            if not chunk:
                continue
            bytes_written += len(chunk)
            if bytes_written > max_bytes:
                msg = f"File too large. Maximum: {settings.max_upload_size_mb} MB"
                raise ValueError(msg)
            f.write(chunk)
    return bytes_written
