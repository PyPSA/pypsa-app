import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_current_user, get_db, get_networks_or_404
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.models import User
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.schemas.plot import PlotRequest
from pypsa_app.backend.tasks import get_plot_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=TaskQueuedResponse)
def generate_plot(
    request: PlotRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate plot from PyPSA network or NetworkCollection statistics"""
    networks = get_networks_or_404(db, request.network_ids, user)
    file_paths = [net.file_path for net in networks]

    return queue_task(
        get_plot_task,
        file_paths=file_paths,
        statistic=request.statistic,
        plot_type=request.plot_type,
        parameters=request.parameters,
    )
