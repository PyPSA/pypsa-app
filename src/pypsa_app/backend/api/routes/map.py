import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from pypsa_app.backend.api.deps import get_current_user, get_network_or_404
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.models import Network, User
from pypsa_app.backend.schemas.common import TaskResponse
from pypsa_app.backend.settings import settings
from pypsa_app.backend.tasks import extract_geographic_layer_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/config")
def get_map_config():
    """Get map configuration including Mapbox token"""
    return {
        "mapbox_token": settings.mapbox_token or "",
    }


@router.get("/{network_id}/buses", response_model=TaskResponse)
def get_buses(
    network: Network = Depends(get_network_or_404),
    user: User = Depends(get_current_user),
):
    """Get network buses as tabular data for map visualization"""
    return queue_task(
        extract_geographic_layer_task, file_path=network.file_path, layer_type="buses"
    )


@router.get("/{network_id}/lines", response_model=TaskResponse)
def get_lines(
    network: Network = Depends(get_network_or_404),
    user: User = Depends(get_current_user),
):
    """Get network lines as tabular data for map visualization"""
    return queue_task(
        extract_geographic_layer_task, file_path=network.file_path, layer_type="lines"
    )


@router.get("/{network_id}/topology.svg")
def get_network_topology_svg(
    network: Network = Depends(get_network_or_404),
    user: User = Depends(get_current_user),
):
    """Get SVG network topology visualization"""
    if not network.topology_svg:
        raise HTTPException(
            status_code=404, detail="Network topology SVG has not been generated yet"
        )

    logger.debug(
        "Returning stored topology SVG",
        extra={
            "network_id": str(network.id),
            "svg_size": len(network.topology_svg),
        },
    )
    return Response(content=network.topology_svg, media_type="image/svg+xml")
