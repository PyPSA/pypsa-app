import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, get_networks, require_permission
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.flows import get_statistics_flow
from pypsa_app.backend.models import Permission, User
from pypsa_app.backend.ratelimit import limiter
from pypsa_app.backend.schemas.statistics import StatisticsParams
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=TaskQueuedResponse)
@limiter.limit(settings.ratelimit_expensive)
async def get_statistics(
    request: Request,
    response: Response,
    body: StatisticsParams,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Get raw statistics data without plotting"""
    networks = get_networks(db, body.network_ids, user)
    file_paths = [net.file_path for net in networks]

    return await queue_task(
        get_statistics_flow,
        file_paths=file_paths,
        statistic=body.statistic,
        parameters=body.parameters,
    )
