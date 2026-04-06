"""Permission utilities for access control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pypsa_app.backend.models import Network, Permission, Run, UserRole, Visibility

if TYPE_CHECKING:
    from pypsa_app.backend.models import User


_ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: {
        Permission.NETWORKS_VIEW,
        Permission.NETWORKS_MODIFY,
        Permission.NETWORKS_MANAGE_ALL,
        Permission.RUNS_VIEW,
        Permission.RUNS_MODIFY,
        Permission.RUNS_MANAGE_ALL,
        Permission.USERS_MANAGE,
        Permission.SYSTEM_MANAGE,
    },
    UserRole.USER: {
        Permission.NETWORKS_VIEW,
        Permission.NETWORKS_MODIFY,
        Permission.RUNS_VIEW,
        Permission.RUNS_MODIFY,
    },
    UserRole.BOT: {
        Permission.NETWORKS_VIEW,
        Permission.NETWORKS_MODIFY,
        Permission.RUNS_VIEW,
        Permission.RUNS_MODIFY,
    },
    UserRole.PENDING: set(),
}


def get_role_permissions() -> dict[UserRole, set[Permission]]:
    return _ROLE_PERMISSIONS


def get_user_permissions(user: User) -> set[Permission]:
    return _ROLE_PERMISSIONS.get(user.role, set())


def has_permission(user: User, permission: Permission) -> bool:
    return permission in get_user_permissions(user)


@dataclass(frozen=True)
class ResourcePerms:
    view: Permission
    modify: Permission
    manage_all: Permission


RESOURCE_PERMS: dict[type, ResourcePerms] = {
    Network: ResourcePerms(
        Permission.NETWORKS_VIEW,
        Permission.NETWORKS_MODIFY,
        Permission.NETWORKS_MANAGE_ALL,
    ),
    Run: ResourcePerms(
        Permission.RUNS_VIEW,
        Permission.RUNS_MODIFY,
        Permission.RUNS_MANAGE_ALL,
    ),
}


def can_access(user: User, resource: Network | Run) -> bool:
    """Can user view this resource? True if public, owner, shared, or admin."""
    perms = RESOURCE_PERMS[type(resource)]
    if (
        resource.visibility == Visibility.PUBLIC
        or resource.user_id == user.id
        or has_permission(user, perms.manage_all)
    ):
        return True

    # Check if the network is shared with this user
    if isinstance(resource, Network) and hasattr(resource, "shared_user_ids"):
        return user.id in resource.shared_user_ids

    return False


def can_modify(user: User, resource: Network | Run) -> bool:
    """Can user modify this resource? True if owner or admin."""
    perms = RESOURCE_PERMS[type(resource)]
    return resource.user_id == user.id or has_permission(user, perms.manage_all)
