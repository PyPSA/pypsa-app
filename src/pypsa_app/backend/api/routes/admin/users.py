"""Admin user management routes.

Includes CRUD, activity stats, user-scoped api-keys, and user-side mirrors
of the user↔backend many-to-many relationship.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, get_user, require_permission
from pypsa_app.backend.api.pagination import (
    FilteredListParams,
    apply_pagination,
    list_meta,
)
from pypsa_app.backend.filters import (
    FieldMap,
    FieldSpec,
    apply_filter_to_query,
    enum_coercer,
)
from pypsa_app.backend.models import (
    ApiKey,
    Network,
    Permission,
    Run,
    SnakedispatchBackend,
    User,
    UserRole,
)
from pypsa_app.backend.schemas.api_key import ApiKeyResponse
from pypsa_app.backend.schemas.auth import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
)
from pypsa_app.backend.schemas.backend import BackendAssign, BackendResponse
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.stats import UserStatsResponse
from pypsa_app.backend.services.email import send_account_approved_email

router = APIRouter()
logger = logging.getLogger(__name__)


_USER_FIELD_MAP: FieldMap = {
    "role": FieldSpec(User.role, enum_coercer(UserRole)),
}


@router.get("/users", response_model=UserListResponse)
def list_users(
    filters: FilteredListParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserListResponse:
    """List all users"""
    query = select(User)

    query = apply_filter_to_query(
        query,
        filters.filter_q,
        _USER_FIELD_MAP,
        text_fields=(User.username, User.email),
    )

    users_query, total = apply_pagination(
        query,
        User,
        filters,
        session=db,
        allowed_sort_fields={"created_at", "username", "email", "last_login", "role"},
    )
    users = db.scalars(users_query).all()

    return UserListResponse(
        data=users,
        meta=list_meta(total, filters, len(users)),
    )


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user_detail(
    user: User = Depends(get_user),
    _admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Get a single user by ID."""
    return user


@router.get("/users/{user_id}/stats", response_model=UserStatsResponse)
def get_user_stats(
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserStatsResponse:
    """Aggregated activity stats for a single user."""
    user_id = user.id

    net_row = db.execute(
        select(
            func.count(Network.id),
            func.coalesce(func.sum(Network.file_size), 0),
            func.max(Network.created_at),
        ).where(Network.user_id == user_id)
    ).one()
    networks_count, total_storage_bytes, max_network_created = net_row

    run_rows = db.execute(
        select(Run.status, func.count())
        .where(Run.user_id == user_id)
        .group_by(Run.status)
    ).all()
    runs_by_status = {str(status): count for status, count in run_rows}
    runs_total = sum(runs_by_status.values())

    backend_rows = db.execute(
        select(SnakedispatchBackend.name, func.count())
        .join(Run, Run.backend_id == SnakedispatchBackend.id)
        .where(Run.user_id == user_id)
        .group_by(SnakedispatchBackend.name)
    ).all()
    runs_by_backend = dict(backend_rows)

    max_run_created = db.scalar(
        select(func.max(Run.created_at)).where(Run.user_id == user_id)
    )

    max_api_key_used = db.scalar(
        select(func.max(ApiKey.last_used_at)).where(ApiKey.user_id == user_id)
    )

    candidates = [
        user.last_login,
        max_network_created,
        max_run_created,
        max_api_key_used,
    ]
    last_activity = max((c for c in candidates if c is not None), default=None)

    return UserStatsResponse(
        networks_count=networks_count,
        runs_total=runs_total,
        runs_by_status=runs_by_status,
        runs_by_backend=runs_by_backend,
        total_storage_bytes=int(total_storage_bytes),
        last_activity=last_activity,
    )


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Create a user (currently only bot role is supported)."""
    if body.role != UserRole.BOT:
        raise HTTPException(400, "Only bot users can be created via API")

    existing = db.scalars(select(User).where(User.username == body.username)).first()
    if existing:
        raise HTTPException(409, "Username already taken")

    user = User(username=body.username, role=body.role, avatar_url=body.avatar_url)
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "User created: %s (role=%s) by %s",
        user.username,
        body.role,
        admin.username,
    )
    return user


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    role_update: UserRoleUpdate,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Update user role"""
    if user.id == admin.id and role_update.role != UserRole.ADMIN:
        raise HTTPException(400, "Cannot remove your own admin role")

    old_role = user.role
    user.role = role_update.role
    db.commit()
    db.refresh(user)

    logger.info(
        "User role updated: %s (%s -> %s) by %s",
        user.username,
        old_role,
        user.role,
        admin.username,
    )

    return user


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Approve a pending user"""
    if user.role != UserRole.PENDING:
        raise HTTPException(
            400,
            f"User is not pending approval (current role: {user.role.value})",
        )

    user.role = UserRole.USER
    db.commit()
    db.refresh(user)

    logger.info("User approved: %s by %s", user.username, admin.username)

    if user.email:
        background_tasks.add_task(
            send_account_approved_email,
            user.username,
            user.email,
        )

    return user


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> dict:
    """Delete a user"""
    if user.id == admin.id:
        raise HTTPException(400, "Cannot delete yourself")

    username = user.username
    db.delete(user)
    db.commit()

    logger.info("User deleted: %s by %s", username, admin.username)

    return {"message": f"User {username} deleted successfully"}


# --- User-side many-to-many mirrors and user-scoped api-keys ---


@router.get("/users/{user_id}/backends", response_model=list[BackendResponse])
def list_user_backends(
    user: User = Depends(get_user),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> list[SnakedispatchBackend]:
    """List backends assigned to a user."""
    return user.backends


@router.post("/users/{user_id}/backends", response_model=MessageResponse)
def assign_backend_to_user(
    body: BackendAssign,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Assign a backend to a user (mirror of POST /backends/{id}/users)."""
    backend = db.get(SnakedispatchBackend, body.backend_id)
    if not backend:
        raise HTTPException(404, "Backend not found")

    if backend in user.backends:
        raise HTTPException(409, "Backend already assigned to this user")

    user.backends.append(backend)
    db.commit()
    logger.info("Backend %s assigned to user %s", backend.name, user.username)
    return {"message": f"Backend {backend.name} assigned to user {user.username}"}


@router.delete("/users/{user_id}/backends/{backend_id}", response_model=MessageResponse)
def unassign_backend_from_user(
    backend_id: UUID,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Remove a backend from a user.

    Mirror of DELETE /backends/{id}/users/{user_id}.
    """
    backend = db.get(SnakedispatchBackend, backend_id)
    if not backend:
        raise HTTPException(404, "Backend not found")

    if backend not in user.backends:
        raise HTTPException(404, "Backend is not assigned to this user")

    user.backends.remove(backend)
    db.commit()
    logger.info("Backend %s unassigned from user %s", backend.name, user.username)
    return {"message": f"Backend {backend.name} removed from user {user.username}"}


@router.get("/users/{user_id}/api-keys", response_model=list[ApiKeyResponse])
def list_user_api_keys(
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> list[ApiKey]:
    """List API keys owned by a user."""
    return db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    ).all()
