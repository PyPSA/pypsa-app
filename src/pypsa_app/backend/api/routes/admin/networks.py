"""Admin network management routes (bypasses owner/visibility rules)."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.api.pagination import (
    FilteredListParams,
    apply_pagination,
    list_meta,
)
from pypsa_app.backend.api.utils.network import delete_network
from pypsa_app.backend.filters import (
    FieldMap,
    FieldSpec,
    apply_filter_to_query,
    enum_coercer,
    name_to_id,
)
from pypsa_app.backend.models import Network, Permission, User, Visibility
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.network import (
    NetworkAdminUpdate,
    NetworkListResponse,
    NetworkResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_admin_network_field_map(db: Session) -> FieldMap:
    return {
        "visibility": FieldSpec(Network.visibility, enum_coercer(Visibility)),
        "owner": FieldSpec(Network.user_id, name_to_id(db, User, "username", "user")),
    }


@router.get("/networks", response_model=NetworkListResponse)
def list_all_networks(
    filters: FilteredListParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> NetworkListResponse:
    """List ALL networks (admin only) - bypasses normal visibility rules"""
    query = select(Network).options(joinedload(Network.owner))

    query = apply_filter_to_query(
        query,
        filters.filter_q,
        _build_admin_network_field_map(db),
        text_fields=(Network.filename, Network.name),
    )

    networks_query, total = apply_pagination(
        query,
        Network,
        filters,
        session=db,
        allowed_sort_fields={"created_at", "name", "filename", "file_size"},
    )
    networks = db.scalars(networks_query).all()

    return NetworkListResponse(
        data=networks,
        meta=list_meta(total, filters, len(networks)),
    )


@router.patch("/networks/{network_id}", response_model=NetworkResponse)
def update_network_admin(
    network_id: UUID,
    body: NetworkAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> Network:
    """Update network properties (admin only) - can change owner, visibility, name"""
    network = db.scalars(
        select(Network)
        .options(joinedload(Network.owner))
        .where(Network.id == network_id)
    ).first()

    if not network:
        raise HTTPException(404, "Network not found")

    # Track changes for logging
    changes = []

    # Update user_id (owner)
    if body.user_id is not None:
        old_owner = network.owner.username
        new_owner = db.get(User, body.user_id)
        if not new_owner:
            raise HTTPException(400, "Specified owner does not exist")
        network.user_id = body.user_id
        changes.append(f"owner: {old_owner} -> {new_owner.username}")
    elif "user_id" in body.model_fields_set:
        raise HTTPException(400, "Cannot set owner to null")

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
    remove_file: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> dict:
    """Delete any network (admin only)"""
    network = db.get(Network, network_id)
    if not network:
        raise HTTPException(404, "Network not found")

    message = delete_network(network, db, remove_file=remove_file)
    logger.info("Network deleted by admin: %s by %s", network.filename, admin.username)
    return {"message": message}
