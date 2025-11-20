import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_current_user, get_db, get_network_or_404
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.models import Network, User
from pypsa_app.backend.schemas.common import MessageResponse, TaskResponse
from pypsa_app.backend.schemas.network import (
    NetworkListResponse,
    NetworkSchema,
)
from pypsa_app.backend.settings import settings
from pypsa_app.backend.tasks import scan_networks_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.put("/", response_model=TaskResponse)
def scan_networks(user: User = Depends(get_current_user)):
    """Scan file system for network files and update database"""
    return queue_task(scan_networks_task, networks_path=str(settings.networks_path))


@router.get("/", response_model=NetworkListResponse)
def list_networks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all networks with pagination."""
    # Build base query
    query = db.query(Network)

    # When auth is enabled, filter by ownership or public networks
    if settings.enable_auth:
        query = query.filter(
            or_(
                Network.user_id == user.id,  # User's own networks
                Network.is_public == True,  # noqa: E712
                Network.user_id == None,  # noqa: E711  # Legacy networks without owner
            )
        )

    # Get total count and paginated results
    total = query.count()
    networks = query.order_by(Network.created_at.desc()).offset(skip).limit(limit).all()

    return NetworkListResponse(
        data=networks,
        meta={"total": total, "skip": skip, "limit": limit, "count": len(networks)},
    )


@router.get("/{network_id}", response_model=NetworkSchema)
def get_network(
    network: Network = Depends(get_network_or_404),
    user: User = Depends(get_current_user),
):
    """Get network by ID"""
    return network


@router.delete("/{network_id}", response_model=MessageResponse)
def delete_network(
    network: Network = Depends(get_network_or_404),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete network from database and file system"""
    # When auth is enabled, only allow deletion if user owns the network
    if settings.enable_auth and user is not None:
        if network.user_id != user.id and network.user_id is not None:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this network",
            )

    # Delete file from disk
    file_path = Path(network.file_path)
    if file_path.exists():
        file_path.unlink()
        logger.info(
            "Deleted network file",
            extra={
                "network_id": str(network.id),
                "file_path": str(file_path),
                "filename": network.filename,
            },
        )

    # Delete from database
    db.delete(network)
    db.commit()

    return {
        "message": f"Network {network.id} and file {network.filename} deleted successfully"
    }
