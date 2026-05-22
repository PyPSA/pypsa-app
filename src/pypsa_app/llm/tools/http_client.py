"""Shared httpx.AsyncClient used by tool implementations to call REST endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from pypsa_app.backend.settings import Settings
    from pypsa_app.llm.tools.base import ToolContext


def build_internal_http_client(settings: Settings) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient pointed at the app's own REST API.

    The base URL is resolved from ``settings.llm``:

    * If ``llm_internal_api_base`` is explicitly set, that value is used
      directly.
    * Otherwise the client defaults to
      ``http://127.0.0.1:{llm_internal_port}`` (port 8000 by default).

    The returned client has a 30-second timeout.  Tool implementations
    forward the user's auth cookie on each call so that all per-user
    auth, permission, and ownership checks apply automatically.
    """
    base = settings.llm.resolved_internal_api_base
    return httpx.AsyncClient(base_url=base, timeout=30.0, follow_redirects=True)


def cookies_for(ctx: ToolContext) -> dict[str, str] | None:
    """Return a cookie dict for internal HTTP calls forwarding the user's session.

    When ``ctx.auth_cookie`` is set, returns ``{"pypsa_session": ctx.auth_cookie}``
    so the called endpoint sees the same authenticated user. The cookie name
    must match SESSION_COOKIE_NAME in backend/settings.py.
    Returns ``None`` when there is no auth cookie (e.g. unauthenticated or
    no session established).
    """
    return {"pypsa_session": ctx.auth_cookie} if ctx.auth_cookie else None
