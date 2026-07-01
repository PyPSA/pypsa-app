"""Task response schemas"""

from typing import Any

from pydantic import BaseModel


class TaskQueuedResponse(BaseModel):
    """Response when a task is queued"""

    task_id: str
    status_url: str
    message: str = "Task queued. Poll status_url for results."


class TaskStatusResponse(BaseModel):
    """Response when polling task status"""

    task_id: str
    state: str
    message: str | None = None
    result: Any | None = None
    error: str | None = None


class TaskResultResponse(BaseModel):
    """Unified result model for completed tasks"""

    status: str  # "success" or "error"
    task_id: str
    generated_at: str | None = None
    data: Any | None = None
    request: dict[str, Any] | None = None
    error: str | None = None
