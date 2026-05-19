"""Per route rate limiting via slowapi.

Keyed by `user:<id>` for authenticated non demo users, otherwise by client IP.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from pypsa_app.backend.settings import settings

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    if settings.trust_cloudflare_ip:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit_key(request: Request) -> str:
    user = getattr(request.state, "user", None) if hasattr(request, "state") else None
    if user is not None and getattr(user, "username", None) != "demo":
        return f"user:{user.id}"
    return f"ip:{get_client_ip(request)}"


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=settings.redis_url,
    enabled=bool(settings.ratelimit_enabled),
    swallow_errors=True,
    headers_enabled=True,
    strategy="moving-window",
    default_limits=[settings.ratelimit_default],
)


class APIRateLimitMiddleware(SlowAPIMiddleware):
    """Apply slowapi's middleware-level rate limit only to /api/* paths."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        return await super().dispatch(request, call_next)


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return 429 with Retry-After + X-RateLimit-* headers, log the hit."""
    key = rate_limit_key(request)
    logger.warning(
        "Rate limit exceeded",
        extra={
            "path": request.url.path,
            "method": request.method,
            "key": key,
            "limit": str(exc.detail),
        },
    )
    response = JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded. Retry after {exc.detail}."},
    )
    limit_info = getattr(request.state, "view_rate_limit", None)
    if limit_info is not None:
        response = request.app.state.limiter._inject_headers(response, limit_info)
    return response
