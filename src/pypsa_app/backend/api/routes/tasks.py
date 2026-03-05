"""Generic task status endpoint for all Celery tasks"""

from uuid import UUID

from fastapi import APIRouter, Depends

from pypsa_app.backend.api.deps import get_active_user
from pypsa_app.backend.api.utils.task_utils import get_task_status_response
from pypsa_app.backend.models import User
from pypsa_app.backend.schemas.task import TaskStatusResponse

router = APIRouter()


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: UUID, user: User = Depends(get_active_user)) -> dict:
    """Get status of any background Celery task.

    States:
    - PENDING: Task is waiting to be processed
    - PROGRESS: Task is running (includes progress metadata)
    - SUCCESS: Task completed successfully
    - FAILURE: Task failed with error
    """
    return get_task_status_response(str(task_id))
