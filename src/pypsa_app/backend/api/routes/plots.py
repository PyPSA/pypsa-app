import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, get_networks, require_permission
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.models import Permission, User
from pypsa_app.backend.schemas.plot import ExploreRequest, PlotRequest
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.tasks import get_explore_task, get_plot_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=TaskQueuedResponse)
def generate_plot(
    request: PlotRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Generate plot from PyPSA network or NetworkCollection statistics"""
    networks = get_networks(db, request.network_ids, user)
    file_paths = [net.file_path for net in networks]

    return queue_task(
        get_plot_task,
        file_paths=file_paths,
        statistic=request.statistic,
        plot_type=request.plot_type,
        parameters=request.parameters,
    )


@router.post("/explore", response_model=TaskQueuedResponse)
def generate_explore(
    request: ExploreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Generate interactive map from PyPSA network using n.plot.explore()"""
    networks = get_networks(db, [request.network_id], user)
    file_paths = [net.file_path for net in networks]

    parameters: dict = {}
    if request.branch_components is not None:
        parameters["branch_components"] = request.branch_components
    if request.geometry:
        parameters["geometry"] = True

    return queue_task(
        get_explore_task,
        file_paths=file_paths,
        parameters=parameters,
    )
