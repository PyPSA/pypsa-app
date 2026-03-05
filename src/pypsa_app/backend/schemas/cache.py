"""Cache response schemas"""

from pydantic import BaseModel

from pypsa_app.backend.schemas.common import MessageResponse


class RedisStatsResponse(BaseModel):
    available: bool
    total_keys: int
    keys_by_type: dict[str, int]
    memory_used: str | None = None


class CachedNetworkEntry(BaseModel):
    file_path: str
    cached_at: str


class NetworkCacheStatsResponse(BaseModel):
    size: int
    max_size: int
    ttl_seconds: int
    hits: int
    misses: int
    hit_rate_percent: float
    cached_networks: list[CachedNetworkEntry]


class ClearCacheResponse(MessageResponse):
    deleted_keys: int
