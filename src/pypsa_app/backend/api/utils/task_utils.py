"""Shared utilities for task status responses"""

import logging

from pypsa_app.backend.task_queue import task_app
from pypsa_app.backend.settings import API_V1_PREFIX

logger = logging.getLogger(__name__)


def get_task_status_response(task_id: str) -> dict:
    """Get standardized task status response"""
    # Check if using Celery or in-memory queue
    try:
        # Try using Celery's AsyncResult if Celery is the backend
        from celery.result import AsyncResult

        task = AsyncResult(task_id, app=task_app)
    except (ImportError, AttributeError):
        # Fall back to in-memory AsyncResult
        from pypsa_app.backend.task_queue import InMemoryAsyncResult

        task = InMemoryAsyncResult(task_id)

    response = {"task_id": task_id, "state": task.state}

    match task.state:
        case "PENDING":
            response["status"] = "Task is waiting to be executed"
        case "PROGRESS":
            info = task.info or {}
            response["status"] = info.get("status", "Processing...")
            if current := info.get("current"):
                response["current"] = current
            if total := info.get("total"):
                response["total"] = total
        case "SUCCESS":
            response["result"] = task.result
        case "FAILURE":
            response["error"] = str(task.info)
        case _:
            response["status"] = str(task.info)

    return response


def queue_task(celery_task, *args, **kwargs) -> dict:
    """
    Queue Celery task and return standard response.

    Args:
        celery_task: Celery task to queue
        *args, **kwargs: Arguments for the task

    Returns:
        Standard task response dict
    """
    task = celery_task.apply_async(args=args, kwargs=kwargs)
    logger.debug(
        "Queued Celery task",
        extra={
            "task_name": celery_task.name,
            "task_id": task.id,
        },
    )

    return {
        "status": "processing",
        "task_id": task.id,
        "status_url": f"{API_V1_PREFIX}/tasks/status/{task.id}",
        "message": "Task queued. Poll status_url for results.",
    }
