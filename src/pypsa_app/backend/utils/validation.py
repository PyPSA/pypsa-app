"""Input validation utilities (paths, URLs) to prevent traversal and SSRF."""

import ipaddress
import logging
import socket
import urllib.parse
from pathlib import Path
from typing import Annotated

from fastapi import HTTPException, status
from pydantic import AfterValidator, HttpUrl

from pypsa_app.backend.settings import settings

logger = logging.getLogger(__name__)


def _check_exists(path: Path) -> None:
    """Raise 404 if path does not exist."""
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"File not found: {path.name}")


def validate_path(
    file_path: str | Path, base_dir: Path | None = None, must_exist: bool = False
) -> Path:
    """Validate file path is within base directory."""
    base_dir = base_dir or settings.networks_path

    try:
        path = Path(file_path).resolve()
        base = base_dir.resolve()

        path.relative_to(base)  # Raises ValueError otherwise

    except ValueError:
        logger.exception(
            "Path traversal attempt detected",
            extra={
                "file_path": str(file_path),
                "base_dir": str(base_dir),
                "resolved_path": str(path) if "path" in locals() else None,
            },
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Access denied: Path outside allowed directory"
        ) from None
    except HTTPException:
        raise

    if must_exist:
        _check_exists(path)

    return path


def validate_url_external(url: str) -> None:
    """Verify that url does not resolve to a private or reserved address.

    Raises ValueError with a user-safe message on failure.
    """
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        msg = "URL has no hostname"
        raise ValueError(msg)

    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        msg = f"Cannot resolve hostname: {hostname}"
        raise ValueError(msg) from exc

    for _family, _type, _proto, _canon, sockaddr in infos:
        addr = ipaddress.ip_address(sockaddr[0])
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            msg = "URLs pointing to internal or reserved networks are not allowed"
            raise ValueError(msg)


def _validate_external_url(url: HttpUrl) -> HttpUrl:
    validate_url_external(str(url))
    return url


ExternalHttpUrl = Annotated[HttpUrl, AfterValidator(_validate_external_url)]
"""HttpUrl that rejects private, loopback, and reserved networks (SSRF guard)."""
