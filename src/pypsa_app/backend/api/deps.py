"""FastAPI dependencies"""

import logging
from collections.abc import Awaitable, Callable, Generator
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.auth.authenticate import resolve_current_user
from pypsa_app.backend.database import SessionLocal
from pypsa_app.backend.models import (
    Network,
    Permission,
    Run,
    SnakedispatchBackend,
    User,
    UserRole,
    Visibility,
)
from pypsa_app.backend.permissions import (
    RESOURCE_PERMS,
    can_access,
    can_modify,
    has_permission,
)

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session]:
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
    """Return authenticated user or None, never blocking requests."""
    return resolve_current_user(request, db)


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


def _require_user_with_permission(user: User | None, permission: Permission) -> User:
    """Validate user is authenticated and has permission. Raises 401/403."""
    if user is None:
        raise HTTPException(401, "Authentication required. Please log in.")
    if user.role == UserRole.PENDING:
        raise HTTPException(403, "Your account is pending approval.")
    if not has_permission(user, permission):
        raise HTTPException(403, "You don't have permission to perform this action.")
    return user


def require_permission(
    permission: Permission,
) -> Callable[..., Awaitable[User]]:
    """Require a specific permission for the endpoint."""

    async def checker(
        user: User | None = Depends(get_current_user_optional),
    ) -> User:
        return _require_user_with_permission(user, permission)

    return checker


AccessLevel = Literal["read", "modify"]


@dataclass
class Authorized[T]:
    """Bundle of a resource and the authenticated user who accessed it."""

    model: T
    user: User


def require_run(
    access: AccessLevel = "read",
) -> Callable[..., Awaitable[Authorized[Run]]]:
    """Authenticate, check permission, fetch run, check access."""
    perms = RESOURCE_PERMS[Run]
    permission = perms.view if access == "read" else perms.modify
    access_check = can_access if access == "read" else can_modify

    async def _dep(
        run_id: UUID = Path(..., description="Run UUID"),
        db: Session = Depends(get_db),
        user: User | None = Depends(get_current_user_optional),
    ) -> Authorized[Run]:
        user = _require_user_with_permission(user, permission)

        run = (
            db.query(Run)
            .options(
                joinedload(Run.owner),
                joinedload(Run.backend),
                joinedload(Run.networks),
            )
            .filter(Run.job_id == run_id)
            .first()
        )
        if not run or not access_check(user, run):
            raise HTTPException(404, "Run not found")

        return Authorized(model=run, user=user)

    return _dep


def require_network(
    access: AccessLevel = "read",
) -> Callable[..., Awaitable[Authorized[Network]]]:
    """Authenticate, check permission, fetch network, check access."""
    perms = RESOURCE_PERMS[Network]
    permission = perms.view if access == "read" else perms.modify
    access_check = can_access if access == "read" else can_modify

    async def _dep(
        network_id: UUID = Path(..., description="Network UUID"),
        db: Session = Depends(get_db),
        user: User | None = Depends(get_current_user_optional),
    ) -> Authorized[Network]:
        user = _require_user_with_permission(user, permission)

        network = (
            db.query(Network)
            .options(joinedload(Network.owner))
            .filter(Network.id == network_id)
            .first()
        )
        if not network or not access_check(user, network):
            raise HTTPException(404, "Network not found")

        return Authorized(model=network, user=user)

    return _dep


async def require_public_run(
    run_id: UUID = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
) -> Run:
    """Fetch a public run by UUID. No auth required.

    Returns 404 for missing or private runs.
    """
    run = (
        db.query(Run)
        .options(
            joinedload(Run.owner),
            joinedload(Run.backend),
            joinedload(Run.networks),
        )
        .filter(Run.job_id == run_id, Run.visibility == Visibility.PUBLIC)
        .first()
    )
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def get_networks(
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
            if not can_access(user, network):
                raise HTTPException(404, "One or more networks not found")

    return networks


def get_backend(
    backend_id: UUID = Path(..., description="Backend UUID"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> SnakedispatchBackend:
    """Fetch backend by ID."""
    backend = (
        db.query(SnakedispatchBackend)
        .filter(SnakedispatchBackend.id == backend_id)
        .first()
    )
    if not backend:
        raise HTTPException(404, "Backend not found")
    return backend


__all__ = [
    "Authorized",
    "get_active_user",
    "get_backend",
    "get_current_user_optional",
    "get_db",
    "get_networks",
    "require_network",
    "require_permission",
    "require_public_run",
    "require_run",
]
