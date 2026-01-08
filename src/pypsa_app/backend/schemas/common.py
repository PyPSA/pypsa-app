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
