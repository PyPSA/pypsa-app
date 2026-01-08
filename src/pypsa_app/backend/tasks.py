"""Celery tasks for long-running PyPSA operations"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from pypsa_app.backend.cache import cache
from pypsa_app.backend.task_queue import task_app
from pypsa_app.backend.schemas.task import TaskResultResponse
from pypsa_app.backend.services.map import extract_geographic_layer
from pypsa_app.backend.services.network import scan_networks
from pypsa_app.backend.services.statistics import get_plot as get_plot_service
from pypsa_app.backend.services.statistics import (
    get_statistics as get_statistics_service,
)
from pypsa_app.backend.settings import settings

logger = logging.getLogger(__name__)


def _execute_task(self, name: str, func: Callable, **kwargs) -> Dict[str, Any]:
    """Execute task with progress tracking, error handling, and result formatting"""
    self.update_state(state="PROGRESS", meta={"status": f"{name} in progress"})
    try:
        data = func(**kwargs)
        return TaskResultResponse(
            status="success",
            task_id=self.request.id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data=data,
            request=kwargs,
        ).model_dump()
    except Exception as e:
        logger.error(
            f"{name} failed",
            extra={
                "task_id": self.request.id,
                "error": str(e),
                "error_type": type(e).__name__,
                **kwargs,
            },
            exc_info=True,
        )
        return TaskResultResponse(
            status="error", task_id=self.request.id, error=str(e)
        ).model_dump()


@task_app.task(bind=True, name="tasks.get_statistics")
def get_statistics_task(self, **kwargs):
    """Background task for statistics generation"""
    func = cache("statistics", ttl=settings.plot_cache_ttl)(get_statistics_service)
    return _execute_task(self, "Statistics generation", func, **kwargs)


@task_app.task(bind=True, name="tasks.get_plot")
def get_plot_task(self, **kwargs):
    """Background task for plot generation"""
    func = cache("plot", ttl=settings.plot_cache_ttl)(get_plot_service)
    return _execute_task(self, "Plot generation", func, **kwargs)


@task_app.task(bind=True, name="tasks.extract_geographic_layer")
def extract_geographic_layer_task(self, **kwargs):
    """Background task for geographic layer extraction"""
    func = cache("map_data", ttl=settings.map_cache_ttl)(extract_geographic_layer)
    return _execute_task(self, "Geographic layer extraction", func, **kwargs)


@task_app.task(bind=True, name="tasks.scan_networks")
def scan_networks_task(self, **kwargs):
    """Background task for network scanning (no caching)"""
    return _execute_task(self, "Network scan", scan_networks, **kwargs)
