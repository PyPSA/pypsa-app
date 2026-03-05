import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, get_networks_or_404, require_permission
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.models import Permission, User
from pypsa_app.backend.schemas.statistics import StatisticsRequest
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.tasks import get_statistics_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=TaskQueuedResponse)
def get_statistics(
    request: StatisticsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Get raw statistics data without plotting"""
    networks = get_networks_or_404(db, request.network_ids, user)
    file_paths = [net.file_path for net in networks]

    return queue_task(
        get_statistics_task,
        file_paths=file_paths,
        statistic=request.statistic,
        parameters=request.parameters,
    )
