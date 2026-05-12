"""Identity resolution: API key validation, session lookup, auth-disabled mode."""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from pypsa_app.backend.auth.session import get_session_store
from pypsa_app.backend.models import ApiKey, User, UserRole
from pypsa_app.backend.settings import SESSION_COOKIE_NAME, settings

logger = logging.getLogger(__name__)

_auth_disabled_user: User | None = None


def set_auth_disabled_user(user: User) -> None:
    """Store a pre created system user for auth disabled mode."""
    if settings.enable_auth:
        msg = "Cannot set auth-disabled user when authentication is enabled"
        raise RuntimeError(msg)
    global _auth_disabled_user  # noqa: PLW0603
    _auth_disabled_user = user


def ensure_system_user(db: Session) -> User:
    """Return the system admin user, creating it if missing.

    Only callable when authentication is disabled. The returned user is also
    registered as the implicit caller for auth-disabled requests.
    """
    if settings.enable_auth:
        msg = "Cannot create system user when authentication is enabled"
        raise RuntimeError(msg)
    system_user = db.scalars(select(User).where(User.username == "system")).first()
    if not system_user:
        system_user = User(username="system", role=UserRole.ADMIN)
        db.add(system_user)
        db.commit()
        db.refresh(system_user)
    set_auth_disabled_user(system_user)
    return system_user


def hash_api_key(token: str) -> str:
    """SHA-256 hash of a raw API key token."""
    return hashlib.sha256(token.encode()).hexdigest()


def _authenticate_api_key(token: str, db: Session) -> User | None:
    """Authenticate a Bearer token and return the linked user, or None."""
    key_hash = hash_api_key(token)
    api_key = db.scalars(select(ApiKey).where(ApiKey.key_hash == key_hash)).first()
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


def resolve_current_user(request: Request, db: Session) -> User | None:
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
                user = db.get(User, user_id)
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
