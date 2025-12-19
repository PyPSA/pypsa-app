"""Permission constants for access control."""

from enum import Enum

from pypsa_app.backend.models import User


class Permission(str, Enum):
    ADMIN = "admin"
    VIEW_NETWORKS = "view_networks"
    CREATE_NETWORKS = "create_networks"
    DELETE_NETWORKS = "delete_networks"


def has_permission(user: User | None, permission: Permission) -> bool:
    """Check if user has a specific permission."""
    if user is None:
        return False
    return permission.value in user.permissions
