"""Prefect worker entrypoint: serves all flow deployments and executes them."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from pypsa_app.backend.settings import PREFECT_DEPLOYMENT_NAME

logger = logging.getLogger(__name__)

_SERVER_TIMEOUT = 120
_RETRY_INTERVAL = 3


async def _wait_for_server() -> None:
    import httpx  # noqa: PLC0415

    from pypsa_app.backend.settings import settings  # noqa: PLC0415

    url = f"{settings.prefect_api_url}/health"
    deadline = time.monotonic() + _SERVER_TIMEOUT
    logger.info("Waiting for Prefect server at %s ...", url)
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=5)
                if resp.status_code == 200:  # noqa: PLR2004
                    logger.info("Prefect server is ready")
                    return
        except Exception:
            logger.debug("Prefect server not ready yet, retrying...")
        await asyncio.sleep(_RETRY_INTERVAL)
    msg = f"Prefect server did not become ready within {_SERVER_TIMEOUT}s"
    raise TimeoutError(msg)


async def _main() -> None:
    from prefect import aserve  # noqa: PLC0415

    from pypsa_app.backend.flows import (  # noqa: PLC0415
        get_explore_flow,
        get_plot_flow,
        get_statistics_flow,
        import_network_from_file_flow,
        import_network_from_url_flow,
        import_run_outputs_flow,
    )

    logging.basicConfig(level=logging.INFO)
    await _wait_for_server()

    concurrency = int(os.environ.get("PREFECT_WORKER_CONCURRENCY", "2"))
    deployments = [
        await flow_fn.ato_deployment(name=PREFECT_DEPLOYMENT_NAME)
        for flow_fn in [
            get_statistics_flow,
            get_plot_flow,
            get_explore_flow,
            import_network_from_file_flow,
            import_network_from_url_flow,
            import_run_outputs_flow,
        ]
    ]

    logger.info(
        "Serving %d flow deployments (concurrency=%d)...",
        len(deployments),
        concurrency,
    )
    await aserve(*deployments, limit=concurrency)


if __name__ == "__main__":
    asyncio.run(_main())
