"""Redis-based session management"""

import logging
import secrets
from urllib.parse import urlparse
from uuid import UUID

from starlette.responses import Response

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from pypsa_app.backend.settings import SESSION_COOKIE_NAME, settings

logger = logging.getLogger(__name__)


class SessionStore:
    """Redis-based session storage for user authentication"""

    def __init__(self) -> None:
        """Initialize Redis connection for sessions"""
        if not REDIS_AVAILABLE:
            msg = "Redis is required for authentication but is not installed"
            raise RuntimeError(msg)

        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        logger.info(
            "Session store initialized",
            extra={
                "redis_url": settings.redis_url,
                "session_ttl": settings.session_ttl,
            },
        )

    def create_session(self, user_id: UUID) -> str:
        """Create a new session for a user.

        Args:
            user_id: UUID of the user

        Returns:
            session_id: Cryptographically secure random session ID

        """
        session_id = secrets.token_urlsafe(32)
        session_key = f"session:{session_id}"

        # Store user_id with TTL
        self.redis_client.setex(session_key, settings.session_ttl, str(user_id))

        logger.info(
            "Session created",
            extra={
                "user_id": str(user_id),
                "session_ttl": settings.session_ttl,
            },
        )

        return session_id

    def get_session(self, session_id: str) -> UUID | None:
        """Get user_id from session_id.

        Args:
            session_id: Session identifier

        Returns:
            user_id: UUID of the user if session is valid, None otherwise

        """
        session_key = f"session:{session_id}"
        user_id_str = self.redis_client.get(session_key)

        if user_id_str:
            return UUID(user_id_str)

        return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session (logout).

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if it didn't exist

        """
        session_key = f"session:{session_id}"
        deleted = self.redis_client.delete(session_key)

        if deleted:
            logger.info(
                "Session deleted",
                extra={"session_deleted": True},
            )

        return deleted > 0

    def refresh_session(self, session_id: str) -> bool:
        """Refresh session TTL (extend expiry).

        Args:
            session_id: Session identifier

        Returns:
            True if session was refreshed, False if it didn't exist

        """
        session_key = f"session:{session_id}"

        # Check if session exists
        if not self.redis_client.exists(session_key):
            return False

        # Extend TTL
        self.redis_client.expire(session_key, settings.session_ttl)

        logger.debug(
            "Session refreshed",
            extra={"session_ttl": settings.session_ttl},
        )

        return True

    def ping(self) -> bool:
        """Check if Redis is accessible"""
        try:
            return self.redis_client.ping()
        except Exception:
            return False


# Global session store instance (initialized in main.py when auth is enabled)
session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the global session store instance"""
    if session_store is None:
        msg = "Session store not initialized. Enable authentication in settings."
        raise RuntimeError(msg)
    return session_store


def attach_session_cookie(
    response: Response, user_id: UUID, *, base_url: str, ttl: int
) -> Response:
    """Set the session cookie on any Response (JSON or Redirect)."""
    store = get_session_store()
    session_id = store.create_session(user_id)
    is_localhost = urlparse(base_url).hostname in ("localhost", "127.0.0.1", "::1")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=not is_localhost,
        samesite="lax",
        max_age=ttl,
    )
    return response
