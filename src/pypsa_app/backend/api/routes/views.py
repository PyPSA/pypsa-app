"""API routes for saved dashboard views."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.models import Permission, SavedView, User, Visibility
from pypsa_app.backend.permissions import has_permission
from pypsa_app.backend.schemas.views import (
    SavedViewCreate,
    SavedViewListResponse,
    SavedViewResponse,
    SavedViewUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=SavedViewResponse, status_code=201)
def create_view(
    body: SavedViewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> SavedView:
    """Create a new saved dashboard view."""
    view = SavedView(
        user_id=user.id,
        network_id=body.network_id,
        name=body.name,
        description=body.description,
        visibility=body.visibility,
        config=body.config.model_dump(),
    )
    db.add(view)
    db.commit()
    db.refresh(view)

    logger.info(
        "Saved view created",
        extra={
            "view_id": str(view.id),
            "view_name": view.name,
            "user": user.username,
        },
    )
    return view


@router.get("/", response_model=SavedViewListResponse)
def list_views(
    network_id: UUID | None = Query(None, description="Filter by network ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> SavedViewListResponse:
    """List saved views accessible to the current user."""
    query = db.query(SavedView).options(joinedload(SavedView.owner))

    # Users see their own views + public views
    if not has_permission(user, Permission.NETWORKS_MANAGE_ALL):
        query = query.filter(
            or_(
                SavedView.user_id == user.id,
                SavedView.visibility == Visibility.PUBLIC,
            )
        )

    if network_id:
        query = query.filter(
            or_(
                SavedView.network_id == network_id,
                SavedView.network_id.is_(None),  # Global views apply to any network
            )
        )

    total = query.count()
    views = query.order_by(SavedView.updated_at.desc()).offset(skip).limit(limit).all()

    return SavedViewListResponse(data=views, total=total)


@router.get("/{view_id}", response_model=SavedViewResponse)
def get_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> SavedView:
    """Get a saved view by ID."""
    view = (
        db.query(SavedView)
        .options(joinedload(SavedView.owner))
        .filter(SavedView.id == view_id)
        .first()
    )
    if not view:
        raise HTTPException(404, "View not found")

    # Check access: own views or public
    if (
        view.user_id != user.id
        and view.visibility != Visibility.PUBLIC
        and not has_permission(user, Permission.NETWORKS_MANAGE_ALL)
    ):
        raise HTTPException(404, "View not found")

    return view


@router.patch("/{view_id}", response_model=SavedViewResponse)
def update_view(
    view_id: UUID,
    body: SavedViewUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> SavedView:
    """Update a saved view. Only the owner can update."""
    view = (
        db.query(SavedView)
        .options(joinedload(SavedView.owner))
        .filter(SavedView.id == view_id)
        .first()
    )
    if not view:
        raise HTTPException(404, "View not found")

    if view.user_id != user.id and not has_permission(
        user, Permission.NETWORKS_MANAGE_ALL
    ):
        raise HTTPException(403, "You can only update your own views")

    if body.name is not None:
        view.name = body.name
    if body.description is not None:
        view.description = body.description
    if body.visibility is not None:
        view.visibility = body.visibility
    if body.config is not None:
        view.config = body.config.model_dump()

    db.commit()
    db.refresh(view)
    return view


@router.delete("/{view_id}")
def delete_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Delete a saved view. Only the owner can delete."""
    view = db.query(SavedView).filter(SavedView.id == view_id).first()
    if not view:
        raise HTTPException(404, "View not found")

    if view.user_id != user.id and not has_permission(
        user, Permission.NETWORKS_MANAGE_ALL
    ):
        raise HTTPException(403, "You can only delete your own views")

    db.delete(view)
    db.commit()

    logger.info(
        "Saved view deleted",
        extra={"view_id": str(view_id), "user": user.username},
    )
    return {"message": "View deleted"}
