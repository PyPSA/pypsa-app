"""Admin routes for user management"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.models import User, UserRole
from pypsa_app.backend.permissions import Permission
from pypsa_app.backend.schemas.auth import (
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
)
from pypsa_app.backend.schemas.common import MessageResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 100,
    role: str | None = Query(None, description="Filter by role"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.ADMIN)),
):
    """List all users"""
    query = db.query(User)

    if role:
        try:
            role_enum = UserRole(role)
            query = query.filter(User.role == role_enum)
        except ValueError:
            valid_roles = [r.value for r in UserRole]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role filter. Must be one of: {', '.join(valid_roles)}",
            )

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return UserListResponse(
        data=users,
        meta={"total": total, "skip": skip, "limit": limit, "count": len(users)},
    )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.ADMIN)),
):
    """Update user role"""
    new_role = UserRole(role_update.role)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if str(user.id) == str(admin.id) and new_role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin role")

    old_role = user.role
    user.role = new_role
    db.commit()
    db.refresh(user)

    logger.info(
        f"User role updated: {user.username} ({old_role} -> {user.role}) by {admin.username}"
    )

    return user


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.ADMIN)),
):
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

    logger.info(f"User approved: {user.username} by {admin.username}")

    return user


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.ADMIN)),
):
    """Delete a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    username = user.username
    db.delete(user)
    db.commit()

    logger.info(f"User deleted: {username} by {admin.username}")

    return {"message": f"User {username} deleted successfully"}
