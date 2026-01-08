import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, get_network_or_404, require_permission
from pypsa_app.backend.api.utils.network_utils import (
    delete_network as delete_network_and_file,
)
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.models import Network, NetworkVisibility, Permission, User
from pypsa_app.backend.permissions import can_access_network, can_modify_network
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.network import (
    NetworkListResponse,
    NetworkResponse,
    NetworkUpdate,
)
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.settings import settings
from pypsa_app.backend.tasks import scan_networks_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.put("/", response_model=TaskQueuedResponse)
def scan_networks(user: User = Depends(require_permission(Permission.NETWORKS_SCAN))):
    """Scan file system for network files and update database"""
    return queue_task(scan_networks_task, networks_path=str(settings.networks_path))


@router.get("/", response_model=NetworkListResponse)
def list_networks(
    skip: int = 0,
    limit: int = 100,
    owners: list[str] | None = Query(
        None,
        description="Filter by owner IDs. Use 'system' for networks without owner, 'me' for current user.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
):
    """List networks with pagination and optional filtering."""
    query = db.query(Network).options(joinedload(Network.owner))

    visibility_filter = None
    if settings.enable_auth and user is not None:
        # All users see: own networks + public + system (user_id=None)
        visibility_filter = or_(
            Network.user_id == user.id,
            Network.visibility == NetworkVisibility.PUBLIC,
            Network.user_id == None,  # noqa: E711
        )
        query = query.filter(visibility_filter)

        # Apply owner filter if specified
        if owners:

            def owner_to_condition(owner_id: str):
                if owner_id == "system":
                    return Network.user_id == None  # noqa: E711
                if owner_id == "me":
                    return Network.user_id == user.id
                return Network.user_id == owner_id

            query = query.filter(or_(*[owner_to_condition(oid) for oid in owners]))

    total = query.count()
    networks = query.order_by(Network.created_at.desc()).offset(skip).limit(limit).all()

    # Get all unique owners for filter dropdown
    all_owners = []
    if settings.enable_auth and user is not None:
        owners_query = db.query(Network.user_id).filter(Network.user_id != None)  # noqa: E711
        if visibility_filter is not None:
            owners_query = owners_query.filter(visibility_filter)
        owner_ids = [oid[0] for oid in owners_query.distinct().all()]
        if owner_ids:
            all_owners = db.query(User).filter(User.id.in_(owner_ids)).all()

    return NetworkListResponse(
        data=networks,
        meta={
            "total": total,
            "skip": skip,
            "limit": limit,
            "count": len(networks),
            "owners": all_owners,
        },
    )


@router.get("/{network_id}", response_model=NetworkResponse)
def get_network(
    network_id: UUID = PathParam(..., description="Network UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
):
    """Get network by ID with owner info"""
    network = (
        db.query(Network)
        .options(joinedload(Network.owner))
        .filter(Network.id == str(network_id))
        .first()
    )

    if not network:
        raise HTTPException(404, "Network not found")

    if settings.enable_auth and not can_access_network(user, network):
        raise HTTPException(404, "Network not found")

    return network


@router.patch("/{network_id}", response_model=NetworkResponse)
def update_network(
    network_id: UUID = PathParam(..., description="Network UUID"),
    body: NetworkUpdate = ...,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_UPDATE)),
):
    """Update network properties. Only owner or admin can update."""
    network = (
        db.query(Network)
        .options(joinedload(Network.owner))
        .filter(Network.id == str(network_id))
        .first()
    )

    if not network:
        raise HTTPException(404, "Network not found")

    if settings.enable_auth and not can_modify_network(user, network):
        raise HTTPException(403, "You can only update your own networks")

    if body.visibility is not None:
        network.visibility = body.visibility
    if body.name is not None:
        network.name = body.name

    db.commit()
    db.refresh(network)

    logger.info(
        "Network updated",
        extra={
            "network_id": str(network.id),
            "updated_by": user.username if user else "anonymous",
        },
    )

    return network


@router.delete("/{network_id}", response_model=MessageResponse)
def delete_network(
    network: Network = Depends(get_network_or_404),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_DELETE)),
):
    """Delete network from database and file system"""
    if settings.enable_auth and not can_modify_network(user, network):
        raise HTTPException(403, "You don't have permission to delete this network")

    message = delete_network_and_file(network, db)
    return {"message": message}
