"""Common response schemas shared across routes"""

from pydantic import BaseModel


class PaginationMeta(BaseModel):
    """Pagination metadata"""

    total: int
    skip: int
    limit: int
    count: int


class MessageResponse(BaseModel):
    message: str


class TaskResponse(BaseModel):
    status: str
    task_id: str
    status_url: str
    message: str
