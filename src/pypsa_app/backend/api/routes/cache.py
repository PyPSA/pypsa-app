import logging

from fastapi import APIRouter, Depends

from pypsa_app.backend.api.deps import require_permission
from pypsa_app.backend.cache import cache_service
from pypsa_app.backend.models import Permission, User
from pypsa_app.backend.schemas.cache import (
    ClearCacheResponse,
    NetworkCacheStatsResponse,
    RedisStatsResponse,
)
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.services.network import _network_cache

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/redis/stats", response_model=RedisStatsResponse)
def get_redis_stats(
    user: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Get Redis cache statistics"""
    stats = {
        "available": cache_service.ping(),
        "total_keys": 0,
        "keys_by_type": {},
    }

    if stats["available"]:
        # Use scan_iter to avoid blocking Redis
        all_keys = list(cache_service.redis_client.scan_iter(match="*"))
        stats["total_keys"] = len(all_keys)

        # Group by type (plot:*, etc.)
        for key in all_keys:
            key_type = key.split(":")[0]
            stats["keys_by_type"][key_type] = stats["keys_by_type"].get(key_type, 0) + 1

        # Memory usage
        info = cache_service.redis_client.info("memory")
        stats["memory_used"] = info.get("used_memory_human")

    return stats


@router.get("/networks/stats", response_model=NetworkCacheStatsResponse)
def get_network_cache_stats(
    user: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Get in-memory PyPSA network cache statistics"""
    return _network_cache.stats()


@router.delete("/redis/plots", response_model=ClearCacheResponse)
def clear_plot_cache(
    user: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Clear all plot caches"""
    deleted_count = cache_service.clear_plot_cache()
    return {"message": "Cleared all plot caches", "deleted_keys": deleted_count}


@router.delete("/redis/{network_id}", response_model=ClearCacheResponse)
def clear_redis_for_network(
    network_id: str, user: User = Depends(require_permission(Permission.SYSTEM_MANAGE))
) -> dict:
    """Clear Redis cache for a specific network"""
    deleted_count = cache_service.clear_network_cache(network_id)
    return {
        "message": (
            f"Cleared Redis cache for network {network_id} (including all plots)"
        ),
        "deleted_keys": deleted_count,
    }


@router.delete("/redis", response_model=ClearCacheResponse)
def clear_redis_cache(
    user: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Clear all Redis cache"""
    deleted_count = cache_service.clear_all_cache()
    return {"message": "Cleared all Redis cache", "deleted_keys": deleted_count}


@router.delete("/networks", response_model=MessageResponse)
def clear_network_cache(
    user: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Clear in-memory PyPSA network cache"""
    _network_cache.clear()
    logger.info(
        "PyPSA network cache cleared",
        extra={
            "cache_type": "in_memory",
        },
    )
    return {"message": "PyPSA network cache cleared successfully"}
