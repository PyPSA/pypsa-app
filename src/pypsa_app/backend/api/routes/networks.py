import logging
import uuid as _uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import ColumnElement, or_
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import (
    Authorized,
    get_db,
    require_network,
    require_permission,
)
from pypsa_app.backend.api.utils.network_utils import (
    delete_network as delete_network_and_file,
)
from pypsa_app.backend.models import Network, Permission, User, Visibility, network_shares
from pypsa_app.backend.permissions import has_permission
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.network import (
    NetworkListResponse,
    NetworkResponse,
    NetworkShareRequest,
    NetworkShareResponse,
    NetworkUpdate,
)
from pypsa_app.backend.services.network import import_network_file
from pypsa_app.backend.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=NetworkResponse, status_code=201)
def upload_network(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> Network:
    """Upload a network file (.nc) and create a database record."""
    if not file.filename or not file.filename.endswith(".nc"):
        raise HTTPException(400, "Only .nc (NetCDF) files are accepted")

    # Sanitize path
    safe_filename = PurePosixPath(file.filename).name
    if not safe_filename or not safe_filename.endswith(".nc"):
        raise HTTPException(400, "Invalid filename")
    safe_filename = safe_filename[:255]

    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    # Write to temp file with enforced size limit
    user_dir = settings.networks_path / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    tmp = user_dir / f"_upload_{_uuid.uuid4().hex}.tmp"

    bytes_written = 0
    with tmp.open("wb") as f:
        while chunk := file.file.read(8192):
            bytes_written += len(chunk)
            if bytes_written > max_bytes:
                tmp.unlink(missing_ok=True)
                raise HTTPException(
                    413, f"File too large. Maximum: {settings.max_upload_size_mb} MB"
                )
            f.write(chunk)

    try:
        network = import_network_file(tmp, safe_filename, user.id, db)
        db.commit()
        db.refresh(network)

        logger.info(
            "Network uploaded",
            extra={
                "network_id": str(network.id),
                "network_filename": safe_filename,
                "user": user.username,
            },
        )
        return network
    finally:
        tmp.unlink(missing_ok=True)


class NetworkListFilters(BaseModel):
    """Query parameters for filtering the networks list."""

    skip: int = 0
    limit: int = 100
    owners: list[str] | None = Query(
        None,
        description="Filter by owner IDs. Use 'me' for current user.",
    )


@router.get("/", response_model=NetworkListResponse)
def list_networks(
    filters: NetworkListFilters = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> NetworkListResponse:
    """List networks with pagination and optional filtering."""
    query = db.query(Network).options(joinedload(Network.owner))

    visibility_filter = None
    if not has_permission(user, Permission.NETWORKS_MANAGE_ALL):
        # Non-admin users see: own networks + public + shared with them
        shared_ids = (
            db.query(network_shares.c.network_id)
            .filter(network_shares.c.user_id == user.id)
            .subquery()
        )
        visibility_filter = or_(
            Network.user_id == user.id,
            Network.visibility == Visibility.PUBLIC,
            Network.id.in_(shared_ids),
        )
        query = query.filter(visibility_filter)

    # Apply owner filter if specified
    if filters.owners:

        def owner_to_condition(owner_id: str) -> ColumnElement[bool]:
            if owner_id == "me":
                return Network.user_id == user.id
            return Network.user_id == owner_id

        conditions = [owner_to_condition(oid) for oid in filters.owners]
        query = query.filter(or_(*conditions))

    total = query.count()
    networks = (
        query.order_by(Network.created_at.desc())
        .offset(filters.skip)
        .limit(filters.limit)
        .all()
    )

    # Get all unique owners for filter dropdown
    all_owners = []
    owners_query = db.query(Network.user_id)
    if not has_permission(user, Permission.NETWORKS_MANAGE_ALL):
        if visibility_filter is not None:
            owners_query = owners_query.filter(visibility_filter)
        else:
            owners_query = owners_query.filter(Network.user_id == user.id)
    owner_ids = [oid[0] for oid in owners_query.distinct().all()]
    if owner_ids:
        all_owners = db.query(User).filter(User.id.in_(owner_ids)).all()

    return NetworkListResponse(
        data=networks,
        meta={
            "total": total,
            "skip": filters.skip,
            "limit": filters.limit,
            "count": len(networks),
            "owners": all_owners,
        },
    )


@router.get("/{network_id}", response_model=NetworkResponse)
def get_network(
    auth: Authorized[Network] = Depends(require_network("read")),
) -> Network:
    """Get network by ID with owner info"""
    return auth.model


@router.patch("/{network_id}", response_model=NetworkResponse)
def update_network(
    body: NetworkUpdate,
    auth: Authorized[Network] = Depends(require_network("modify")),
    db: Session = Depends(get_db),
) -> Network:
    """Update network properties. Only owner or admin can update."""
    network = auth.model

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
            "updated_by": auth.user.username,
        },
    )

    return network


@router.delete("/{network_id}", response_model=MessageResponse)
def delete_network(
    auth: Authorized[Network] = Depends(require_network("modify")),
    db: Session = Depends(get_db),
) -> dict:
    """Delete network from database and file system"""
    message = delete_network_and_file(auth.model, db)
    return {"message": message}


# --- Sharing endpoints ---


@router.get("/{network_id}/shares", response_model=NetworkShareResponse)
def get_network_shares(
    auth: Authorized[Network] = Depends(require_network("modify")),
) -> dict:
    """Get list of users this network is shared with. Owner only."""
    network = auth.model
    return {
        "network_id": network.id,
        "shared_with": network.shared_with,
    }


@router.post("/{network_id}/shares", response_model=NetworkShareResponse)
def share_network(
    body: NetworkShareRequest,
    auth: Authorized[Network] = Depends(require_network("modify")),
    db: Session = Depends(get_db),
) -> dict:
    """Share a network with another user. Owner only."""
    network = auth.model
    target_user = db.query(User).filter(User.id == body.user_id).first()
    if not target_user:
        raise HTTPException(404, "User not found")

    if target_user.id == auth.user.id:
        raise HTTPException(400, "Cannot share a network with yourself")

    if target_user in network.shared_with:
        raise HTTPException(400, "Network is already shared with this user")

    network.shared_with.append(target_user)
    db.commit()
    db.refresh(network)

    logger.info(
        "Network shared",
        extra={
            "network_id": str(network.id),
            "shared_with": target_user.username,
            "shared_by": auth.user.username,
        },
    )
    return {
        "network_id": network.id,
        "shared_with": network.shared_with,
    }


@router.delete("/{network_id}/shares/{user_id}", response_model=NetworkShareResponse)
def unshare_network(
    user_id: _uuid.UUID,
    auth: Authorized[Network] = Depends(require_network("modify")),
    db: Session = Depends(get_db),
) -> dict:
    """Remove a user's access to a shared network. Owner only."""
    network = auth.model
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user or target_user not in network.shared_with:
        raise HTTPException(404, "User not found in share list")

    network.shared_with.remove(target_user)
    db.commit()
    db.refresh(network)

    logger.info(
        "Network unshared",
        extra={
            "network_id": str(network.id),
            "unshared_from": target_user.username,
            "unshared_by": auth.user.username,
        },
    )
    return {
        "network_id": network.id,
        "shared_with": network.shared_with,
    }
