"""Redis cache infrastructure and decorator"""

import hashlib
import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from pypsa_app.backend.settings import settings
from pypsa_app.backend.utils.serializers import fast_json_dumps, fast_json_loads

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


def cache(key_template: str, ttl: int) -> Callable:
    """Cache decorator for FastAPI endpoints.

    Args:
        key_template: Template string with {param_name} placeholders
                     Example: "map_buses:{network_id}"
                     For Pydantic models, use fields: "plot:{request.statistic}"
        ttl: Time to live in seconds

    """

    def decorator(func: Callable) -> Callable:
        param_names = list(inspect.signature(func).parameters.keys())

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Zip args to param names
            values = dict(zip(param_names, args, strict=False))
            values.update(kwargs)

            # Simple approach: serialize all values and hash
            serializable = {}
            for key, value in values.items():
                if hasattr(value, "model_dump"):
                    serializable[key] = value.model_dump()
                else:
                    serializable[key] = value

            # Generate cache key by hashing all parameters
            cache_hash = hashlib.md5(  # noqa: S324
                fast_json_dumps(serializable).encode()
            ).hexdigest()[:12]
            cache_key = f"{key_template.split(':', maxsplit=1)[0]}:{cache_hash}"

            # Check cache
            cached_data = cache_service.get(cache_key)
            if cached_data:
                logger.debug("Cache hit", extra={"cache_key": cache_key})
                return cached_data

            # Cache miss - call function and cache result
            logger.debug("Cache miss", extra={"cache_key": cache_key})
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


class CacheService:
    """Generic Redis cache service"""

    def __init__(self) -> None:
        """Initialize Redis connection"""
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        logger.info(
            "Connected to Redis",
            extra={
                "redis_url": settings.redis_url,
                "decode_responses": True,
            },
        )

    def get(self, key: str) -> dict | None:
        """Get cached data by key"""
        cached_data = self.redis_client.get(key)
        if cached_data:
            return fast_json_loads(cached_data)
        return None

    def set(self, key: str, value: dict, ttl: int) -> bool:
        """Set cached data with TTL"""
        serialized = fast_json_dumps(value)
        size_bytes = len(serialized)
        size_mb = size_bytes / (1024 * 1024)

        self.redis_client.setex(key, ttl, serialized)
        logger.info(
            "Cached data (%.2f MB)",
            size_mb,
            extra={
                "cache_key": key,
                "ttl": ttl,
                "size_mb": round(size_mb, 2),
            },
        )
        return True

    def _clear_by_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern and return the count."""
        deleted = 0
        for key in self.redis_client.scan_iter(match=pattern):
            self.redis_client.delete(key)
            deleted += 1
        if deleted > 0:
            logger.info("Cleared %d cache entries matching '%s'", deleted, pattern)
        return deleted

    def clear_plot_cache(self) -> int:
        """Clear all plot caches"""
        return self._clear_by_pattern("plot:*")

    def clear_network_cache(self, network_id: str) -> int:
        """Clear all cached data for a specific network (clears all plots)"""
        return self._clear_by_pattern("plot:*")

    def clear_all_cache(self) -> int:
        """Clear all cached data"""
        return self._clear_by_pattern("*")

    def ping(self) -> bool:
        """Check if Redis is accessible"""
        return self.redis_client.ping()


class DummyCacheService:
    """Dummy cache service when Redis is not available"""

    def __init__(self) -> None:
        logger.warning(
            "Redis not available - using dummy cache",
            extra={
                "cache_enabled": False,
                "reason": "Redis not available",
            },
        )

    def get(self, *args: Any, **kwargs: Any) -> None:
        return None

    def set(self, *args: Any, **kwargs: Any) -> bool:
        return False

    def clear_plot_cache(self) -> int:
        return 0

    def clear_network_cache(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def clear_all_cache(self) -> int:
        return 0

    def ping(self) -> bool:
        return False


# Global cache service instance
if REDIS_AVAILABLE and settings.redis_url:
    try:
        cache_service = CacheService()
    except Exception as e:
        logger.exception(
            "Failed to initialize Redis cache",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "redis_url": settings.redis_url,
                "fallback": "DummyCacheService",
            },
        )
        cache_service = DummyCacheService()
else:
    cache_service = DummyCacheService()
