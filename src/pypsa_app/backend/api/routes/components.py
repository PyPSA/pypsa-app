"""API routes for browsing and editing network component data."""

import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import (
    Authorized,
    get_db,
    require_network,
)
from pypsa_app.backend.models import Network
from pypsa_app.backend.schemas.components import (
    ComponentDataResponse,
    ComponentListResponse,
    ComponentSummary,
    ComponentTimeseriesResponse,
    ComponentUpdateRequest,
)
from pypsa_app.backend.services.network import NetworkService, _network_cache
from pypsa_app.backend.utils.path_validation import validate_path
from pypsa_app.backend.utils.serializers import _sanitize_float

router = APIRouter()
logger = logging.getLogger(__name__)

EXCLUDED_SUFFIXES = ("Type",)


def _load_network(network: Network, *, use_cache: bool = True) -> NetworkService:
    """Load a PyPSA network from its file path."""
    return NetworkService(network.file_path, use_cache=use_cache)


def _find_component(n, component_name: str):
    """Find a component by name or list_name. Raises 404 if not found."""
    for c in n.components:
        if c.name == component_name or c.list_name == component_name:
            return c
    raise HTTPException(404, f"Component '{component_name}' not found in network")


def _get_dynamic_attrs(n, list_name: str) -> list[str]:
    """Get non-empty time-varying attribute names for a component."""
    dynamic_attr = f"{list_name}_t"
    if not hasattr(n, dynamic_attr):
        return []

    dynamic_store = getattr(n, dynamic_attr)
    attrs = []
    # Use pandas-based iteration over known DataFrame attributes
    # rather than dir() which can expose internal Python attributes
    for attr_name in dynamic_store:
        try:
            attr_val = getattr(dynamic_store, attr_name, None)
            if isinstance(attr_val, pd.DataFrame) and len(attr_val) > 0:
                attrs.append(attr_name)
        except Exception:
            continue
    return sorted(attrs)


@router.get("/{network_id}/components", response_model=ComponentListResponse)
def list_components(
    auth: Authorized[Network] = Depends(require_network("read")),
) -> ComponentListResponse:
    """List all component types in a network with their counts and attributes."""
    service = _load_network(auth.model)
    n = service.n

    components = []
    for c in n.components:
        if c.name.endswith(EXCLUDED_SUFFIXES):
            continue
        if len(c) == 0:
            continue

        static_df = getattr(n, c.list_name)
        dynamic_attrs = _get_dynamic_attrs(n, c.list_name)

        components.append(
            ComponentSummary(
                name=c.name,
                list_name=c.list_name,
                count=len(c),
                category=getattr(c, "category", None) or None,
                attrs=list(static_df.columns),
                has_dynamic=len(dynamic_attrs) > 0,
                dynamic_attrs=dynamic_attrs,
            )
        )

    # Sort by count descending
    components.sort(key=lambda c: c.count, reverse=True)

    return ComponentListResponse(
        components=components,
        total_components=len(components),
    )


@router.get(
    "/{network_id}/components/{component_name}",
    response_model=ComponentDataResponse,
)
def get_component_data(
    component_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_desc: bool = Query(False, description="Sort descending"),
    search: str | None = Query(None, description="Filter rows by index substring"),
    auth: Authorized[Network] = Depends(require_network("read")),
) -> ComponentDataResponse:
    """Get paginated static data for a specific component type."""
    service = _load_network(auth.model)
    n = service.n

    component = _find_component(n, component_name)
    df = getattr(n, component.list_name).copy()

    # Apply search filter on index (literal substring match, not regex)
    if search:
        mask = df.index.astype(str).str.contains(
            search, case=False, na=False, regex=False
        )
        df = df[mask]

    total = len(df)

    # Apply sorting
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=not sort_desc, na_position="last")

    # Paginate
    df_page = df.iloc[skip : skip + limit]

    # Sanitize values for JSON
    data = []
    for _, row in df_page.iterrows():
        data.append([_sanitize_float(v) for v in row.tolist()])

    dtypes = {col: str(df[col].dtype) for col in df.columns}

    return ComponentDataResponse(
        component=component.name,
        columns=list(df.columns),
        index=[str(idx) for idx in df_page.index],
        data=data,
        dtypes=dtypes,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{network_id}/components/{component_name}/timeseries/{attr}",
    response_model=ComponentTimeseriesResponse,
)
def get_component_timeseries(
    component_name: str,
    attr: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    auth: Authorized[Network] = Depends(require_network("read")),
) -> ComponentTimeseriesResponse:
    """Get time-varying data for a specific component attribute."""
    service = _load_network(auth.model)
    n = service.n

    component = _find_component(n, component_name)

    dynamic_attr = f"{component.list_name}_t"
    if not hasattr(n, dynamic_attr):
        raise HTTPException(404, f"No time-varying data for '{component_name}'")

    dynamic_store = getattr(n, dynamic_attr)
    if not hasattr(dynamic_store, attr):
        raise HTTPException(
            404, f"Attribute '{attr}' not found in {component_name} time series"
        )

    ts_df = getattr(dynamic_store, attr)
    if not isinstance(ts_df, pd.DataFrame) or len(ts_df) == 0:
        raise HTTPException(
            404, f"No data for '{attr}' in {component_name} time series"
        )

    total_snapshots = len(ts_df)
    ts_page = ts_df.iloc[skip : skip + limit]

    data = []
    for _, row in ts_page.iterrows():
        data.append([_sanitize_float(v) for v in row.tolist()])

    return ComponentTimeseriesResponse(
        component=component.name,
        attr=attr,
        columns=[str(c) for c in ts_page.columns],
        index=[str(idx) for idx in ts_page.index],
        data=data,
        total_snapshots=total_snapshots,
        skip=skip,
        limit=limit,
    )


@router.patch("/{network_id}/components/{component_name}")
def update_component_data(
    component_name: str,
    body: ComponentUpdateRequest,
    auth: Authorized[Network] = Depends(require_network("modify")),
    db: Session = Depends(get_db),
) -> dict:
    """Update static data for specific component rows.

    Loads a fresh (uncached) copy, applies changes, exports to disk,
    then invalidates only the affected cache entry.
    """
    # Load fresh copy to avoid mutating shared cached objects
    service = _load_network(auth.model, use_cache=False)
    n = service.n

    component = _find_component(n, component_name)
    df = getattr(n, component.list_name)

    # Validate all indices exist
    missing = [idx for idx in body.updates if idx not in df.index]
    if missing:
        raise HTTPException(404, f"Component indices not found: {missing}")

    # Validate all columns exist
    all_columns = set()
    for changes in body.updates.values():
        all_columns.update(changes.keys())
    invalid_cols = all_columns - set(df.columns)
    if invalid_cols:
        raise HTTPException(400, f"Invalid columns: {list(invalid_cols)}")

    # Apply updates
    changes_count = 0
    for idx, changes in body.updates.items():
        for col, value in changes.items():
            df.at[idx, col] = value
            changes_count += 1

    # Validate and export to file
    safe_path = validate_path(Path(auth.model.file_path), must_exist=True)
    n.export(safe_path)

    # Invalidate only the affected network in cache
    with _network_cache._lock:
        _network_cache.cache.pop(str(safe_path), None)

    logger.info(
        "Component data updated",
        extra={
            "network_id": str(auth.model.id),
            "component": component_name,
            "changes_count": changes_count,
            "updated_by": auth.user.username,
        },
    )

    return {"message": f"Updated {changes_count} values in {component_name}"}
