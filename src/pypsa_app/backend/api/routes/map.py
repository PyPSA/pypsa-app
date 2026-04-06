"""API routes for network geographic/map data."""

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Query

from pypsa_app.backend.api.deps import (
    Authorized,
    require_network,
)
from pypsa_app.backend.models import Network
from pypsa_app.backend.services.network import NetworkService

router = APIRouter()
logger = logging.getLogger(__name__)


def _load_network(network: Network) -> NetworkService:
    return NetworkService(network.file_path, use_cache=True)


def _extract_bus_features(n, carriers: list[str] | None = None) -> list[dict]:
    """Extract bus positions as GeoJSON Point features."""
    buses = n.buses
    if carriers:
        buses = buses[buses.carrier.isin(carriers)]

    features = []
    for idx, row in buses.iterrows():
        x, y = row.get("x"), row.get("y")
        if pd.isna(x) or pd.isna(y) or (x == 0 and y == 0):
            continue
        props: dict[str, Any] = {"name": str(idx)}
        for col in ("carrier", "v_nom", "country"):
            if col in row.index:
                val = row[col]
                if pd.notna(val):
                    props[col] = (
                        float(val) if isinstance(val, (int, float)) else str(val)
                    )
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(x), float(y)]},
                "properties": props,
            }
        )
    return features


def _extract_branch_features(n, component: str, buses_df: pd.DataFrame) -> list[dict]:
    """Extract branch (Line/Link) data as GeoJSON LineString features."""
    df = getattr(n, component, None)
    if df is None or len(df) == 0:
        return []

    features = []
    for idx, row in df.iterrows():
        bus0_name, bus1_name = row.get("bus0"), row.get("bus1")
        if bus0_name not in buses_df.index or bus1_name not in buses_df.index:
            continue

        bus0 = buses_df.loc[bus0_name]
        bus1 = buses_df.loc[bus1_name]

        coords = []
        for bus in (bus0, bus1):
            x, y = bus.get("x"), bus.get("y")
            if pd.isna(x) or pd.isna(y):
                break
            coords.append([float(x), float(y)])

        if len(coords) != 2:
            continue

        props: dict[str, Any] = {
            "name": str(idx),
            "bus0": str(bus0_name),
            "bus1": str(bus1_name),
            "type": component.rstrip("s"),  # "lines" -> "line", "links" -> "link"
        }

        # Add capacity info
        if "s_nom" in row.index and pd.notna(row["s_nom"]):
            props["capacity"] = float(row["s_nom"])
        elif "p_nom" in row.index and pd.notna(row["p_nom"]):
            props["capacity"] = float(row["p_nom"])

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": props,
            }
        )
    return features


@router.get("/{network_id}/map")
def get_map_data(
    carriers: list[str] | None = Query(None, description="Filter buses by carrier"),
    auth: Authorized[Network] = Depends(require_network("read")),
) -> dict:
    """Get GeoJSON data for network visualization on a map.

    Returns buses as Points and lines/links as LineStrings.
    """
    service = _load_network(auth.model)
    n = service.n

    buses = n.buses
    bus_features = _extract_bus_features(n, carriers)
    line_features = _extract_branch_features(n, "lines", buses)
    link_features = _extract_branch_features(n, "links", buses)

    # Compute bounds for map centering
    xs = [f["geometry"]["coordinates"][0] for f in bus_features]
    ys = [f["geometry"]["coordinates"][1] for f in bus_features]

    bounds = None
    if xs and ys:
        bounds = {
            "southwest": [min(ys), min(xs)],
            "northeast": [max(ys), max(xs)],
        }

    return {
        "buses": {
            "type": "FeatureCollection",
            "features": bus_features,
        },
        "branches": {
            "type": "FeatureCollection",
            "features": line_features + link_features,
        },
        "bounds": bounds,
        "total_buses": len(bus_features),
        "total_branches": len(line_features) + len(link_features),
    }
