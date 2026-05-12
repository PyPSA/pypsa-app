"""Common response schemas shared across routes"""

from pydantic import BaseModel


class ListMeta(BaseModel):
    """List endpoint metadata: pagination offsets and counts."""

    total: int
    offset: int
    limit: int
    count: int


class MessageResponse(BaseModel):
    message: str
