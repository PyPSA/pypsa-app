"""Task response schemas"""

from typing import Any, Literal

from pydantic import BaseModel


class TaskQueuedResponse(BaseModel):
    """Response when a task is queued"""

    task_id: str
    status_url: str
    message: str = "Task queued. Poll status_url for results."


class TaskStatusResponse(BaseModel):
    """Response when polling task status"""

    task_id: str
    state: Literal["PENDING", "PROGRESS", "SUCCESS", "FAILURE"]
    message: str | None = None
    current: int | None = None
    total: int | None = None
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
