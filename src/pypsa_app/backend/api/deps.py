"""FastAPI dependencies"""

import hashlib
import logging
from collections.abc import Awaitable, Callable, Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from pypsa_app.backend.auth.session import get_session_store
from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.models import ApiKey, Network, Permission, User, UserRole
from pypsa_app.backend.permissions import can_access_network, has_permission
from pypsa_app.backend.settings import SESSION_COOKIE_NAME, settings

logger = logging.getLogger(__name__)

_auth_disabled_user: User | None = None


def set_auth_disabled_user(user: User) -> None:
    """Store a pre-created system user for auth-disabled mode."""
    if settings.enable_auth:
        msg = "Cannot set auth-disabled user when authentication is enabled"
        raise RuntimeError(msg)
    global _auth_disabled_user  # noqa: PLW0603
    _auth_disabled_user = user


def hash_api_key(token: str) -> str:
    """SHA-256 hash of a raw API key token."""
    return hashlib.sha256(token.encode()).hexdigest()


def get_db() -> Generator[Session]:
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _authenticate_api_key(token: str, db: Session) -> User | None:
    """Authenticate a Bearer token and return the linked user, or None."""
    key_hash = hash_api_key(token)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if not api_key:
        return None

    if api_key.expires_at is not None:
        now = datetime.now(UTC)
        expires = api_key.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < now:
            return None

    # Debounce last_used_at updates to avoid a write on every request
    now = datetime.now(UTC)
    last_used = api_key.last_used_at
    if last_used is not None and last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=UTC)
    if not last_used or (now - last_used) > timedelta(minutes=5):
        api_key.last_used_at = now
        db.commit()

    return api_key.owner


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Return authenticated user or None, never blocking requests."""
    if _auth_disabled_user is not None:
        return _auth_disabled_user

    # Get session cookie
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        try:
            session_store = get_session_store()
            user_id = session_store.get_session(session_id)

            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    logger.debug(
                        "User authenticated: %s (role: %s)",
                        user.username,
                        user.role,
                    )
                    return user
                logger.warning("Session references non-existent user: %s", user_id)
            else:
                logger.debug("Session not found or expired")

        except (ConnectionError, OSError) as e:
            logger.exception("Session store connection error")
            raise HTTPException(
                status_code=503,
                detail="Authentication service temporarily unavailable."
                " Please try again.",
            ) from e

    # No valid session, try API key via Bearer token
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
        user = _authenticate_api_key(token, db)
        if user is not None:
            return user

    return None


async def get_active_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    """Require an active (non PENDING) user. Raises 401/403."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in.",
        )

    if user.role == UserRole.PENDING:
        raise HTTPException(
            status_code=403,
            detail="Your account is pending approval.",
        )

    return user


def require_permission(
    permission: Permission,
) -> Callable[..., Awaitable[User]]:
    """Require a specific permission for the endpoint."""

    async def checker(
        user: User | None = Depends(get_current_user_optional),
    ) -> User:
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please log in.",
            )

        if not has_permission(user, permission):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to perform this action.",
            )

        return user

    return checker


def get_accessible_network(
    network_id: UUID = Path(..., description="Network UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
) -> Network:
    """Fetch network by ID with access control.

    Raises 404 if not found or inaccessible.
    """
    network = db.query(Network).filter(Network.id == str(network_id)).first()
    if not network:
        raise HTTPException(404, "Network not found")

    if not can_access_network(user, network):
        raise HTTPException(404, "Network not found")

    return network


def get_networks_or_404(
    db: Session,
    network_ids: list[str],
    user: User | None = None,
) -> list[Network]:
    """Validate network_ids exist and user has access. Raises 404 if not."""
    networks = db.query(Network).filter(Network.id.in_(network_ids)).all()

    if len(networks) != len(network_ids):
        raise HTTPException(404, "One or more networks not found")

    if user is not None:
        for network in networks:
            if not can_access_network(user, network):
                raise HTTPException(404, "One or more networks not found")

    return networks


__all__ = [
    "Permission",
    "get_active_user",
    "get_current_user_optional",
    "get_db",
    "get_accessible_network",
    "get_networks_or_404",
    "hash_api_key",
    "require_permission",
    "set_auth_disabled_user",
]
