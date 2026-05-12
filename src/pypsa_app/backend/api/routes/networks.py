import logging
from collections.abc import Iterator
from pathlib import PurePosixPath

from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile
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
from pypsa_app.backend.api.utils.network import (
    make_temp_path,
    stream_to_file_with_limit,
)
from pypsa_app.backend.api.utils.task_utils import queue_task
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
    ComponentDataResponse,
    NetworkListResponse,
    NetworkResponse,
    NetworkUpdate,
    ReportsPayload,
)
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.services.network import NetworkService
from pypsa_app.backend.settings import settings
from pypsa_app.backend.tasks import (
    import_network_from_file_task,
    import_network_from_url_task,
)
from pypsa_app.backend.utils.validation import ExternalHttpUrl

router = APIRouter()
logger = logging.getLogger(__name__)


def _iter_upload_file(file: UploadFile, chunk_size: int = 8192) -> Iterator[bytes]:
    while chunk := file.file.read(chunk_size):
        yield chunk


@router.post("/", response_model=TaskQueuedResponse, status_code=202)
def upload_network(
    file: UploadFile,
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> dict:
    """Accept a .nc upload and enqueue import as a background task."""
    if not file.filename or not file.filename.endswith(".nc"):
        raise HTTPException(400, "Only .nc (NetCDF) files are accepted")

    safe_filename = PurePosixPath(file.filename).name
    if not safe_filename or not safe_filename.endswith(".nc"):
        raise HTTPException(400, "Invalid filename")
    safe_filename = safe_filename[:255]

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    tmp = make_temp_path(user.id)
    try:
        stream_to_file_with_limit(_iter_upload_file(file), tmp, max_bytes)
    except ValueError as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(413, str(exc)) from exc
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return queue_task(
        import_network_from_file_task,
        tmp_path=str(tmp),
        original_filename=safe_filename,
        user_id=str(user.id),
    )


@router.post("/from-url", response_model=TaskQueuedResponse, status_code=202)
def create_network_from_url(
    url: ExternalHttpUrl = Body(..., embed=True),
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> dict:
    """Enqueue a task to download ``url`` and import it as a network."""
    url_str = str(url)
    if url.scheme not in {"http", "https"}:
        raise HTTPException(400, "URL must use http or https")
    if not url_str.lower().endswith(".nc"):
        raise HTTPException(400, "URL must point to a .nc file")

    return queue_task(
        import_network_from_url_task,
        url=url_str,
        user_id=str(user.id),
    )


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


@router.get("/{network_id}/reports")
def get_network_reports(
    auth: Authorized[Network] = Depends(require_network("read")),
) -> ReportsPayload | None:
    return auth.model.reports


@router.put("/{network_id}/reports", response_model=ReportsPayload)
def save_network_reports(
    body: ReportsPayload,
    auth: Authorized[Network] = Depends(require_network("modify")),
    db: Session = Depends(get_db),
) -> ReportsPayload:
    network = auth.model
    network.reports = body.model_dump()
    db.commit()
    return body


@router.get(
    "/{network_id}/components/{component_name}",
    response_model=ComponentDataResponse,
)
def get_component_data(
    component_name: str,
    auth: Authorized[Network] = Depends(require_network("read")),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    sort_by: str | None = Query(None),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
) -> ComponentDataResponse:
    network = auth.model
    service = NetworkService(network.file_path)
    n = service.n

    try:
        component = n.components[component_name]
    except KeyError as exc:
        raise HTTPException(404, f"Component '{component_name}' not found") from exc

    df = component.static

    if search:
        # Might wanna add optional regex search at some point
        mask = (
            df.astype(str)
            .apply(
                lambda col: col.str.contains(
                    search, case=False, regex=False, na=False
                )
            )
            .any(axis=1)
        )
        df = df[mask]

    total = len(df)

    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=(sort_dir == "asc"))

    page = df.iloc[offset : offset + limit]

    dtypes = {col: str(dtype) for col, dtype in page.dtypes.items()}
    data = []
    for _, row in page.iterrows():
        data.append(
            [
                None if isinstance(v, float) and (v != v) else v  # noqa: PLR0124
                for v in row.tolist()
            ]
        )

    return ComponentDataResponse(
        component=component_name,
        columns=list(page.columns),
        dtypes=dtypes,
        index=[str(i) for i in page.index],
        data=data,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.delete("/{network_id}", response_model=MessageResponse)
def delete_network(
    auth: Authorized[Network] = Depends(require_network("modify")),
    db: Session = Depends(get_db),
) -> dict:
    """Delete network from database and file system"""
    message = delete_network_and_file(auth.model, db)
    return {"message": message}
