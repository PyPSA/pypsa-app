import logging
import uuid as _uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import (
    Authorized,
    get_db,
    require_network,
    require_permission,
)
from pypsa_app.backend.api.pagination import (
    FilteredListParams,
    apply_pagination,
    list_meta,
)
from pypsa_app.backend.api.utils.network import (
    delete_network as delete_network_and_file,
)
from pypsa_app.backend.filters import (
    FieldMap,
    FieldSpec,
    apply_filter_to_query,
    enum_coercer,
    name_to_id,
)
from pypsa_app.backend.models import Network, Permission, User, Visibility
from pypsa_app.backend.permissions import has_permission
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.network import (
    NetworkListResponse,
    NetworkResponse,
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


def _build_network_field_map(user: User, db: Session) -> FieldMap:
    username_to_id = name_to_id(db, User, "username", "user")
    return {
        "owner": FieldSpec(
            Network.user_id, lambda s: user.id if s == "me" else username_to_id(s)
        ),
        "visibility": FieldSpec(Network.visibility, enum_coercer(Visibility)),
    }


@router.get("/", response_model=NetworkListResponse)
def list_networks(
    filters: FilteredListParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> NetworkListResponse:
    """List networks with pagination and optional filtering."""
    query = select(Network).options(joinedload(Network.owner))

    visibility_filter = None
    if not has_permission(user, Permission.NETWORKS_MANAGE_ALL):
        visibility_filter = or_(
            Network.user_id == user.id,
            Network.visibility == Visibility.PUBLIC,
        )
        query = query.where(visibility_filter)

    query = apply_filter_to_query(
        query,
        filters.filter_q,
        _build_network_field_map(user, db),
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

    # Get all unique owners for filter dropdown
    all_owners = []
    owners_query = select(Network.user_id).distinct()
    if not has_permission(user, Permission.NETWORKS_MANAGE_ALL):
        if visibility_filter is not None:
            owners_query = owners_query.where(visibility_filter)
        else:
            owners_query = owners_query.where(Network.user_id == user.id)
    owner_ids = db.scalars(owners_query).all()
    if owner_ids:
        all_owners = db.scalars(
            select(User).where(User.id.in_(owner_ids))
        ).all()

    return NetworkListResponse(
        data=networks,
        meta={**list_meta(total, filters, len(networks)), "owners": all_owners},
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
