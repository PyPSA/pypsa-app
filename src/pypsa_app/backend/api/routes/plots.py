import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, get_networks, require_permission
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.flows import get_explore_flow, get_plot_flow
from pypsa_app.backend.models import Permission, User
from pypsa_app.backend.ratelimit import limiter
from pypsa_app.backend.schemas.plot import ExploreRequest, PlotParams
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=TaskQueuedResponse)
@limiter.limit(settings.ratelimit_expensive)
async def generate_plot(
    request: Request,
    response: Response,
    body: PlotParams,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Generate plot from PyPSA network or NetworkCollection statistics"""
    networks = get_networks(db, body.network_ids, user)
    file_paths = [net.file_path for net in networks]

    return await queue_task(
        get_plot_flow,
        file_paths=file_paths,
        statistic=body.statistic,
        plot_type=body.plot_type,
        parameters=body.parameters,
    )


@router.post("/explore", response_model=TaskQueuedResponse)
@limiter.limit(settings.ratelimit_expensive)
async def generate_explore(
    request: Request,
    response: Response,
    body: ExploreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Generate interactive map from PyPSA network using n.plot.explore()"""
    networks = get_networks(db, [body.network_id], user)
    file_paths = [net.file_path for net in networks]

    parameters: dict = {}
    if body.branch_components is not None:
        parameters["branch_components"] = body.branch_components
    if body.geometry:
        parameters["geometry"] = True

    return await queue_task(
        get_explore_flow,
        file_paths=file_paths,
        parameters=parameters,
    )
