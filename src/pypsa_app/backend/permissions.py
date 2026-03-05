"""Permission utilities for access control."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypsa_app.backend.models import NetworkVisibility, Permission, UserRole

if TYPE_CHECKING:
    from pypsa_app.backend.models import Network, Run, User


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
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
        Permission.RUNS_VIEW,
        Permission.RUNS_MODIFY,
    },
    UserRole.PENDING: set(),
}


def get_permissions_for_role(role: UserRole) -> set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())


def get_user_permissions(user: User) -> set[Permission]:
    return get_permissions_for_role(user.role)


def has_permission(user: User, permission: Permission) -> bool:
    return permission in get_user_permissions(user)


def can_access_network(user: User, network: Network) -> bool:
    is_public = network.visibility == NetworkVisibility.PUBLIC
    is_system = network.user_id is None
    is_owner = network.user_id == user.id
    is_admin = has_permission(user, Permission.NETWORKS_MANAGE_ALL)
    return is_public or is_system or is_owner or is_admin


def can_modify_network(user: User, network: Network) -> bool:
    is_owner = network.user_id == user.id
    is_admin = has_permission(user, Permission.NETWORKS_MANAGE_ALL)
    return is_owner or is_admin


def can_access_run(user: User, run: Run) -> bool:
    """Check if user can view this run."""
    is_system = run.user_id is None
    is_owner = run.user_id == user.id
    is_admin = has_permission(user, Permission.RUNS_MANAGE_ALL)
    return is_system or is_owner or is_admin


def can_modify_run(user: User, run: Run) -> bool:
    """Check if user can cancel/remove this run."""
    is_owner = run.user_id == user.id
    is_admin = has_permission(user, Permission.RUNS_MANAGE_ALL)
    return is_owner or is_admin
