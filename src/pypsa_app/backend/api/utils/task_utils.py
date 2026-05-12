"""Shared utilities for task status responses"""

import logging
from collections.abc import Callable

from pypsa_app.backend.settings import API_V1_PREFIX
from pypsa_app.backend.task_queue import task_app

logger = logging.getLogger(__name__)


def get_task_status_response(task_id: str) -> dict:
    """Get standardized task status response"""
    # Check if using Celery or in-memory queue
    try:
        # Try using Celery's AsyncResult if Celery is the backend
        from celery.result import AsyncResult  # noqa: PLC0415

        task = AsyncResult(task_id, app=task_app)
    except (ImportError, AttributeError) as e:
        # Fall back to in-memory AsyncResult
        logger.warning("Celery unavailable, using in-memory task queue: %s", e)
        from pypsa_app.backend.task_queue import InMemoryAsyncResult  # noqa: PLC0415

        task = InMemoryAsyncResult(task_id)

    response = {"task_id": task_id, "state": task.state}

    match task.state:
        case "PENDING":
            response["message"] = "Task is waiting to be executed"
        case "PROGRESS":
            info = task.info or {}
            response["message"] = info.get("status", "Processing...")
            if current := info.get("current"):
                response["current"] = current
            if total := info.get("total"):
                response["total"] = total
        case "SUCCESS":
            response["result"] = task.result
        case "FAILURE":
            response["error"] = "Task failed unexpectedly"
        case _:
            response["message"] = "Task in unknown state"

    return response


def queue_task(celery_task: Callable, *args: object, **kwargs: object) -> dict:
    """Queue Celery task and return standard response."""
    task = celery_task.apply_async(args=args, kwargs=kwargs)
    logger.debug(
        "Queued Celery task",
        extra={
            "task_name": celery_task.name,
            "task_id": task.id,
        },
    )

    return {
        "task_id": task.id,
        "status_url": f"{API_V1_PREFIX}/tasks/status/{task.id}",
    }
