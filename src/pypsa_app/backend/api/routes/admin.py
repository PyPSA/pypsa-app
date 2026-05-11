"""Admin routes for user, network, and backend management"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_backend, get_db, require_permission
from pypsa_app.backend.api.utils.network import delete_network
from pypsa_app.backend.models import (
    Network,
    Permission,
    Run,
    SnakedispatchBackend,
    User,
    UserRole,
    Visibility,
)
from pypsa_app.backend.permissions import get_role_permissions
from pypsa_app.backend.schemas.auth import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
)
from pypsa_app.backend.schemas.backend import BackendResponse, UserBackendAssign
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.network import (
    NetworkAdminUpdate,
    NetworkListResponse,
    NetworkResponse,
)
from pypsa_app.backend.schemas.run import (
    RunAdminUpdate,
    RunListResponse,
    RunResponse,
    RunSummary,
)
from pypsa_app.backend.services.backend_registry import backend_registry
from pypsa_app.backend.services.email import send_account_approved_email

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/permissions")
def get_permissions(
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> dict:
    """Get all available permissions and role mappings"""
    return {
        "permissions": [p.value for p in Permission],
        "role_permissions": {
            role.value: [p.value for p in perms]
            for role, perms in get_role_permissions().items()
        },
    }


@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 100,
    role: str | None = Query(None, description="Filter by role"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserListResponse:
    """List all users"""
    query = db.query(User)

    if role:
        try:
            role_enum = UserRole(role)
            query = query.filter(User.role == role_enum)
        except ValueError as e:
            valid_roles = [r.value for r in UserRole]
            raise HTTPException(
                400,
                f"Invalid role filter. Must be one of: {', '.join(valid_roles)}",
            ) from e

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return UserListResponse(
        data=users,
        meta={"total": total, "skip": skip, "limit": limit, "count": len(users)},
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

    existing = db.query(User).filter(User.username == body.username).first()
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
    user_id: UUID,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Update user role"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

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
    user_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Approve a pending user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

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
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> dict:
    """Delete a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if user.id == admin.id:
        raise HTTPException(400, "Cannot delete yourself")

    username = user.username
    db.delete(user)
    db.commit()

    logger.info("User deleted: %s by %s", username, admin.username)

    return {"message": f"User {username} deleted successfully"}


@router.get("/networks", response_model=NetworkListResponse)
def list_all_networks(
    skip: int = 0,
    limit: int = 100,
    visibility: Visibility | None = Query(
        None, description="Filter: 'public' or 'private'"
    ),
    owner: str | None = Query(None, description="Filter by owner user_id"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> NetworkListResponse:
    """List ALL networks (admin only) - bypasses normal visibility rules"""
    query = db.query(Network).options(joinedload(Network.owner))

    if visibility:
        query = query.filter(Network.visibility == visibility)

    # Apply owner filter
    if owner:
        try:
            owner_uuid = UUID(owner)
            query = query.filter(Network.user_id == owner_uuid)
        except ValueError as e:
            raise HTTPException(
                400, "Invalid owner filter. Must be a valid UUID"
            ) from e

    total = query.count()
    networks = query.order_by(Network.created_at.desc()).offset(skip).limit(limit).all()

    return NetworkListResponse(
        data=networks,
        meta={"total": total, "skip": skip, "limit": limit, "count": len(networks)},
    )


@router.patch("/networks/{network_id}", response_model=NetworkResponse)
def update_network_admin(
    network_id: UUID,
    body: NetworkAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> Network:
    """Update network properties (admin only) - can change owner, visibility, name"""
    network = (
        db.query(Network)
        .options(joinedload(Network.owner))
        .filter(Network.id == network_id)
        .first()
    )

    if not network:
        raise HTTPException(404, "Network not found")

    # Track changes for logging
    changes = []

    # Update user_id (owner)
    if body.user_id is not None:
        old_owner = network.owner.username
        new_owner = db.query(User).filter(User.id == body.user_id).first()
        if not new_owner:
            raise HTTPException(400, "Specified owner does not exist")
        network.user_id = body.user_id
        changes.append(f"owner: {old_owner} -> {new_owner.username}")
    elif "user_id" in body.model_fields_set:
        raise HTTPException(400, "Cannot set owner to null")

    # Update visibility
    if body.visibility is not None:
        old_vis = network.visibility.value
        network.visibility = body.visibility
        changes.append(f"visibility: {old_vis} -> {body.visibility.value}")

    # Update name
    if body.name is not None:
        old_name = network.name or "(none)"
        network.name = body.name
        changes.append(f"name: {old_name} -> {body.name}")

    if changes:
        db.commit()
        db.refresh(network)
        logger.info(
            "Network updated by admin: %s - %s by %s",
            network.filename,
            ", ".join(changes),
            admin.username,
        )

    return network


@router.delete("/networks/{network_id}", response_model=MessageResponse)
def delete_network_admin(
    network_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> dict:
    """Delete any network (admin only)"""
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(404, "Network not found")

    message = delete_network(network, db)
    logger.info("Network deleted by admin: %s by %s", network.filename, admin.username)
    return {"message": message}


# --- Run management ---


@router.get("/runs", response_model=RunListResponse)
def list_all_runs(
    skip: int = 0,
    limit: int = 100,
    visibility: Visibility | None = Query(
        None, description="Filter: 'public' or 'private'"
    ),
    owner: str | None = Query(None, description="Filter by owner user_id"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.RUNS_MANAGE_ALL)),
) -> RunListResponse:
    """List ALL runs (admin only) - bypasses normal visibility rules"""
    query = db.query(Run).options(joinedload(Run.owner), joinedload(Run.backend))

    if visibility:
        query = query.filter(Run.visibility == visibility)

    if owner:
        try:
            owner_uuid = UUID(owner)
            query = query.filter(Run.user_id == owner_uuid)
        except ValueError as e:
            raise HTTPException(
                400, "Invalid owner filter. Must be a valid UUID"
            ) from e

    total = query.count()
    runs = query.order_by(Run.created_at.desc()).offset(skip).limit(limit).all()

    return RunListResponse(
        data=[RunSummary.model_validate(r) for r in runs],
        meta={"total": total, "skip": skip, "limit": limit, "count": len(runs)},
    )


@router.patch("/runs/{run_id}", response_model=RunResponse)
def update_run_admin(
    run_id: UUID,
    body: RunAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.RUNS_MANAGE_ALL)),
) -> RunResponse:
    """Update run properties (admin only) - can change owner, visibility"""
    run = (
        db.query(Run)
        .options(
            joinedload(Run.owner), joinedload(Run.backend), joinedload(Run.networks)
        )
        .filter(Run.job_id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(404, "Run not found")

    changes = []

    if body.user_id is not None:
        old_owner = run.owner.username
        new_owner = db.query(User).filter(User.id == body.user_id).first()
        if not new_owner:
            raise HTTPException(400, "Specified owner does not exist")
        run.user_id = body.user_id
        changes.append(f"owner: {old_owner} -> {new_owner.username}")
    elif "user_id" in body.model_fields_set:
        raise HTTPException(400, "Cannot set owner to null")

    if body.visibility is not None:
        old_vis = run.visibility.value
        run.visibility = body.visibility
        changes.append(f"visibility: {old_vis} -> {body.visibility.value}")

    if changes:
        db.commit()
        db.refresh(run)
        logger.info(
            "Run updated by admin: %s - %s by %s",
            run.job_id,
            ", ".join(changes),
            admin.username,
        )

    return RunResponse.model_validate(run)


@router.delete("/runs/{run_id}", response_model=MessageResponse)
def delete_run_admin(
    run_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.RUNS_MANAGE_ALL)),
) -> dict:
    """Delete any run (admin only)"""
    run = db.query(Run).filter(Run.job_id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")

    # Clean up remote job on the execution backend
    client = backend_registry.get_client(run.backend_id)
    if client:
        try:
            client.delete_job(str(run_id))
        except Exception:
            logger.warning("Remote cleanup failed for run %s", run_id, exc_info=True)

    db.delete(run)
    db.commit()
    logger.info("Run deleted by admin: %s by %s", run_id, admin.username)
    return {"message": "Run removed"}


# --- Backend management ---


@router.get("/backends", response_model=list[BackendResponse])
def list_backends(
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> list[SnakedispatchBackend]:
    """List all registered Snakedispatch backends."""
    return db.query(SnakedispatchBackend).order_by(SnakedispatchBackend.name).all()


@router.get("/backends/{backend_id}/users", response_model=list[UserResponse])
def list_backend_users(
    backend: SnakedispatchBackend = Depends(get_backend),
) -> list[User]:
    """List users assigned to a backend."""
    return backend.users


@router.post("/backends/{backend_id}/users", response_model=MessageResponse)
def assign_user_to_backend(
    body: UserBackendAssign,
    db: Session = Depends(get_db),
    backend: SnakedispatchBackend = Depends(get_backend),
) -> dict:
    """Assign a user to a backend."""
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if user in backend.users:
        raise HTTPException(409, "User already assigned to this backend")

    backend.users.append(user)
    db.commit()
    logger.info(
        "User %s assigned to backend %s",
        user.username,
        backend.name,
    )
    return {"message": f"User {user.username} assigned to backend {backend.name}"}


@router.delete("/backends/{backend_id}/users/{user_id}", response_model=MessageResponse)
def unassign_user_from_backend(
    user_id: UUID,
    db: Session = Depends(get_db),
    backend: SnakedispatchBackend = Depends(get_backend),
) -> dict:
    """Remove a user from a backend."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if user not in backend.users:
        raise HTTPException(404, "User is not assigned to this backend")

    backend.users.remove(user)
    db.commit()
    logger.info(
        "User %s unassigned from backend %s",
        user.username,
        backend.name,
    )
    return {"message": f"User {user.username} removed from backend {backend.name}"}
