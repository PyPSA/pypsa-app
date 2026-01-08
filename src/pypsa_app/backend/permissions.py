"""Permission utilities for access control."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypsa_app.backend.models import NetworkVisibility, Permission, UserRole

if TYPE_CHECKING:
    from pypsa_app.backend.models import Network, User


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: {
        Permission.NETWORKS_VIEW,
        Permission.NETWORKS_CREATE,
        Permission.NETWORKS_SCAN,
        Permission.NETWORKS_UPDATE,
        Permission.NETWORKS_DELETE,
        Permission.NETWORKS_VIEW_ALL,
        Permission.USERS_VIEW,
        Permission.USERS_MANAGE,
    },
    UserRole.USER: {
        Permission.NETWORKS_VIEW,
        Permission.NETWORKS_CREATE,
        Permission.NETWORKS_UPDATE,
        Permission.NETWORKS_DELETE,
    },
    UserRole.PENDING: set(),
}


def get_permissions_for_role(role: UserRole) -> set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())


def get_user_permissions(user: User) -> set[Permission]:
    return get_permissions_for_role(user.role)


def has_permission(user: User | None, permission: Permission) -> bool:
    if user is None:
        return False
    return permission in get_user_permissions(user)


def can_access_network(user: User | None, network: Network) -> bool:
    is_public = network.visibility == NetworkVisibility.PUBLIC
    is_system = network.user_id is None
    is_owner = user is not None and network.user_id == user.id
    is_admin = has_permission(user, Permission.NETWORKS_VIEW_ALL)
    return is_public or is_system or is_owner or is_admin


def can_modify_network(user: User | None, network: Network) -> bool:
    is_owner = user is not None and network.user_id == user.id
    is_admin = has_permission(user, Permission.USERS_MANAGE)
    return is_owner or is_admin
