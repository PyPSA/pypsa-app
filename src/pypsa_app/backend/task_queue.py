"""Prefect task queue — submit flows and poll their status."""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class PrefectTaskQueue:
    """Submits flows via Prefect deployments and polls the Prefect server for status."""

    async def submit(self, deployment_name: str, **kwargs: Any) -> str:
        from prefect.deployments import run_deployment  # noqa: PLC0415

        flow_run = await run_deployment(
            deployment_name,
            parameters=kwargs,
            timeout=0,  # fire-and-forget; don't wait for completion
        )
        logger.debug(
            "Submitted Prefect flow run",
            extra={"deployment": deployment_name, "flow_run_id": str(flow_run.id)},
        )
        return str(flow_run.id)

    async def get_status(self, task_id: str) -> dict:
        from prefect.client.orchestration import get_client  # noqa: PLC0415
        from prefect.exceptions import ObjectNotFound  # noqa: PLC0415

        response: dict[str, Any] = {"task_id": task_id}
        try:
            async with get_client() as client:
                flow_run = await client.read_flow_run(uuid.UUID(task_id))
        except ObjectNotFound:
            response["state"] = "NOT_FOUND"
            return response

        state_type = flow_run.state_type
        response["state"] = state_type.value if state_type else "PENDING"

        if state_type:
            if state_type.value == "COMPLETED":
                response["result"] = await flow_run.state.result(raise_on_failure=False)
            elif state_type.value in {"FAILED", "CRASHED"}:
                response["error"] = flow_run.state.message or "Task failed"

        return response


task_queue = PrefectTaskQueue()
