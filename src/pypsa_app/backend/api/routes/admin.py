"""Admin routes for user and network management"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.api.utils.network_utils import delete_network
from pypsa_app.backend.models import (
    Network,
    NetworkVisibility,
    Permission,
    User,
    UserRole,
)
from pypsa_app.backend.permissions import ROLE_PERMISSIONS
from pypsa_app.backend.schemas.auth import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
)
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.network import (
    NetworkAdminUpdate,
    NetworkListResponse,
    NetworkResponse,
)

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
            for role, perms in ROLE_PERMISSIONS.items()
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
                status_code=400,
                detail=f"Invalid role filter. Must be one of: {', '.join(valid_roles)}",
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
        raise HTTPException(
            status_code=400, detail="Only bot users can be created via API"
        )

    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

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
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id and role_update.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin role")

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
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Approve a pending user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != UserRole.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"User is not pending approval (current role: {user.role.value})",
        )

    user.role = UserRole.USER
    db.commit()
    db.refresh(user)

    logger.info("User approved: %s by %s", user.username, admin.username)

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
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    username = user.username
    db.delete(user)
    db.commit()

    logger.info("User deleted: %s by %s", username, admin.username)

    return {"message": f"User {username} deleted successfully"}


@router.get("/networks", response_model=NetworkListResponse)
def list_all_networks(
    skip: int = 0,
    limit: int = 100,
    visibility: str | None = Query(None, description="Filter: 'public' or 'private'"),
    owner: str | None = Query(
        None, description="Filter: 'system' for no owner, or user_id"
    ),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> NetworkListResponse:
    """List ALL networks (admin only) - bypasses normal visibility rules"""
    query = db.query(Network).options(joinedload(Network.owner))

    # Apply visibility filter
    if visibility:
        try:
            vis_enum = NetworkVisibility(visibility)
            query = query.filter(Network.visibility == vis_enum)
        except ValueError as e:
            valid = [v.value for v in NetworkVisibility]
            raise HTTPException(
                400, f"Invalid visibility. Must be one of: {', '.join(valid)}"
            ) from e

    # Apply owner filter
    if owner:
        if owner == "system":
            query = query.filter(Network.user_id == None)  # noqa: E711
        else:
            try:
                owner_uuid = UUID(owner)
                query = query.filter(Network.user_id == owner_uuid)
            except ValueError as e:
                raise HTTPException(
                    400, "Invalid owner filter. Must be 'system' or a valid UUID"
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
        .filter(Network.id == str(network_id))
        .first()
    )

    if not network:
        raise HTTPException(404, "Network not found")

    # Track changes for logging
    changes = []

    # Update user_id (owner) - special handling for "system" (None)
    if body.user_id is not None or "user_id" in body.model_fields_set:
        old_owner = network.owner.username if network.owner else "System"
        if body.user_id is not None:
            new_owner = db.query(User).filter(User.id == body.user_id).first()
            if not new_owner:
                raise HTTPException(400, "Specified owner does not exist")
            new_owner_name = new_owner.username
        else:
            new_owner_name = "System"
        network.user_id = body.user_id
        changes.append(f"owner: {old_owner} -> {new_owner_name}")

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
    network = db.query(Network).filter(Network.id == str(network_id)).first()
    if not network:
        raise HTTPException(404, "Network not found")

    message = delete_network(network, db)
    logger.info("Network deleted by admin: %s by %s", network.filename, admin.username)
    return {"message": message}
