"""Shared utilities for task status responses."""

import logging
from typing import Any

from pypsa_app.backend.settings import API_V1_PREFIX, PREFECT_DEPLOYMENT_NAME
from pypsa_app.backend.task_queue import task_queue

logger = logging.getLogger(__name__)


async def get_task_status_response(task_id: str) -> dict:
    """Return a standardised task status dict for the given task/flow run ID."""
    return await task_queue.get_status(task_id)


async def queue_task(flow: Any, **kwargs: object) -> dict:
    """Submit a flow to the task queue and return the standard queued-task response."""
    deployment_name = f"{flow.name}/{PREFECT_DEPLOYMENT_NAME}"
    flow_run_id = await task_queue.submit(deployment_name, **kwargs)
    logger.debug(
        "Queued flow",
        extra={"deployment": deployment_name, "flow_run_id": flow_run_id},
    )
    return {
        "task_id": flow_run_id,
        "status_url": f"{API_V1_PREFIX}/tasks/status/{flow_run_id}",
    }


async def submit_flow(flow: Any, **kwargs: object) -> str:
    """Submit a flow fire-and-forget; returns the flow run ID."""
    deployment_name = f"{flow.name}/{PREFECT_DEPLOYMENT_NAME}"
    return await task_queue.submit(deployment_name, **kwargs)
