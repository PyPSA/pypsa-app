"""FastAPI dependencies"""

import logging
from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.models import Network, User
from pypsa_app.backend.permissions import Permission, has_permission
from pypsa_app.backend.settings import SESSION_COOKIE_NAME, settings

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """
    Get current user from session cookie if authenticated.
    Returns None if authentication is disabled or user is not authenticated.
    Always allows request to proceed.
    """
    if not settings.enable_auth:
        return None

    # Get session cookie
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None

    # Get user_id from session
    from pypsa_app.backend.auth.session import get_session_store

    try:
        session_store = get_session_store()
        user_id = session_store.get_session(session_id)

        if not user_id:
            return None

        # Load user from database
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return None

        return user

    except Exception as e:
        logger.error(f"Auth check error: {e}", exc_info=True)
        return None


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    """
    Require authentication. Raises 401 if user is not authenticated.
    When authentication is disabled, always allows access.
    """
    if settings.enable_auth and user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in.",
        )

    # When auth is disabled, user will be None but we don't raise an exception
    # This allows the endpoint to proceed without authentication
    return user


def require_permission(permission: Permission):
    """Require a specific permission for the endpoint."""

    async def checker(
        user: User | None = Depends(get_current_user_optional),
    ) -> User:
        # When auth is disabled, allow access
        if not settings.enable_auth:
            return user

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


def get_network_or_404(
    network_id: UUID = Path(..., description="Network UUID"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> Network:
    """
    Validate network_id (UUID format + DB existence) and return Network.
    When auth is enabled, checks that user has access (owns it or it's public).
    """
    network = db.query(Network).filter(Network.id == str(network_id)).first()
    if not network:
        raise HTTPException(404, "Network not found")

    # When auth is enabled, verify user has access to this network
    if settings.enable_auth and user is not None:
        # User can access if they own it, it's public, or it has no owner (legacy)
        has_access = (
            network.user_id == user.id or network.is_public or network.user_id is None
        )
        if not has_access:
            raise HTTPException(404, "Network not found")  # Don't reveal it exists

    return network


def get_networks_or_404(
    db: Session,
    network_ids: list[str],
    user: User | None = None,
) -> list[Network]:
    """
    Validate network_ids (DB existence) and return list of Networks.
    When auth is enabled, checks that user has access to all networks.

    Args:
        db: Database session
        network_ids: List of network UUIDs
        user: Current user (if authenticated)

    Returns:
        List of Network objects

    Raises:
        HTTPException: If networks not found or user lacks access
    """
    networks = db.query(Network).filter(Network.id.in_(network_ids)).all()

    # Check all networks were found
    if len(networks) != len(network_ids):
        raise HTTPException(404, "One or more networks not found")

    # When auth is enabled, verify user has access to all networks
    if settings.enable_auth and user is not None:
        for network in networks:
            has_access = (
                network.user_id == user.id
                or network.is_public
                or network.user_id is None
            )
            if not has_access:
                raise HTTPException(404, "One or more networks not found")

    return networks


__all__ = [
    "get_db",
    "get_network_or_404",
    "get_networks_or_404",
    "get_current_user_optional",
    "get_current_user",
    "require_permission",
    "Permission",
]
