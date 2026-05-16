"""Tool: invoke ONE PyPSA stats method via the async statistics endpoint.

Posts to ``POST /api/v1/statistics/``, polls
``GET /api/v1/tasks/status/{task_id}`` until the Celery task reaches a
terminal state, then post-processes the dataframe or series into a
renderer-friendly payload.

ONE method per call by design. When the LLM wants several methods, it
emits parallel ``tool_calls`` in a single turn.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pypsa_app.backend.utils.allowlists import ALLOWED_STATISTICS
from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult
from pypsa_app.llm.tools.http_client import cookies_for

_UNITS: dict[str, str] = {
    "installed_capacity": "MW (power) or MWh (stores/storage_units)",
    "optimal_capacity": "MW (power) or MWh (stores/storage_units)",
    "expanded_capacity": "MW (power) or MWh (stores/storage_units)",
    "capex": "currency (typically EUR)",
    "installed_capex": "currency (typically EUR)",
    "expanded_capex": "currency (typically EUR)",
    "fom": "currency/year",
    "opex": "currency",
    "system_cost": "currency",
    "supply": "MWh",
    "withdrawal": "MWh",
    "transmission": "MWh",
    "energy_balance": "MWh",
    "capacity_factor": "fraction (0-1)",
    "curtailment": "MWh",
    "revenue": "currency",
    "market_value": "currency/MWh",
    "prices": "currency/MWh",
}

# Methods that depend on optimisation results — empty output usually means
# the network has not been solved.
_REQUIRES_OPTIMISATION: frozenset[str] = frozenset(
    {
        "supply",
        "withdrawal",
        "transmission",
        "energy_balance",
        "capacity_factor",
        "curtailment",
        "revenue",
        "market_value",
        "prices",
        "opex",
        "system_cost",
    }
)

_OPTIONAL_PARAMS: tuple[str, ...] = (
    "groupby",
    "groupby_time",
    "groupby_method",
    "carrier",
    "bus_carrier",
)

class GetNetworkStatisticsTool(Tool):
    """Invoke one PyPSA stats method through the async statistics endpoint."""

    name = "get_network_statistics"
    description = (
        "Get ONE aggregated PyPSA statistics method for a network. Each call "
        "returns a single statistic — emit several tool_calls in one turn "
        "when you need multiple methods.\n\n"
        "Use these by question type:\n"
        "- Capacity: installed_capacity, optimal_capacity, expanded_capacity\n"
        "- Costs: capex, installed_capex, expanded_capex, fom, opex, system_cost\n"
        "- Energy flows: supply, withdrawal, transmission, energy_balance\n"
        "- Performance: capacity_factor, curtailment\n"
        "- Economic: revenue, market_value, prices\n\n"
        "All results are aggregated over time. `groupby` controls the "
        "dimension (carrier/bus/country); `groupby_time` controls temporal "
        "aggregation (sum/mean/max/min). Methods that depend on optimisation "
        "results return empty data with a `network_not_solved` warning when "
        "the network has not been solved."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "network_id": {
                "type": "string",
                "description": "UUID of the network. Get ids from list_networks.",
            },
            "statistic": {
                "type": "string",
                "enum": sorted(ALLOWED_STATISTICS),
                "description": "Which PyPSA stats method to invoke.",
            },
            "groupby": {
                "type": "string",
                "enum": ["carrier", "bus", "country"],
                "description": "How to group results. Default 'carrier'.",
            },
            "groupby_time": {
                "type": "string",
                "enum": ["sum", "mean", "max", "min"],
                "description": "How to aggregate temporal statistics.",
            },
            "groupby_method": {
                "type": "string",
                "enum": ["sum", "mean", "min", "max", "first", "last"],
                "description": "How to aggregate values within the same group.",
            },
            "carrier": {
                "type": "string",
                "description": "Filter to a specific carrier name.",
            },
            "bus_carrier": {
                "type": "string",
                "description": ("Filter to a specific bus carrier (e.g. 'AC', 'DC')."),
            },
            "nice_names": {
                "type": "boolean",
                "description": (
                    "Use human-readable carrier/component names. Default true."
                ),
            },
        },
        "required": ["network_id", "statistic"],
    }

    poll_interval_seconds: float = 0.25
    poll_max_attempts: int = 480  # ~120 s at the default interval

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        network_id = args["network_id"]
        statistic = args["statistic"]

        parameters: dict[str, Any] = {
            k: args[k] for k in _OPTIONAL_PARAMS if args.get(k) is not None
        }
        if "nice_names" in args:
            parameters["nice_names"] = args["nice_names"]

        cookies = cookies_for(ctx)
        queued = await self._http.post(
            "/api/v1/statistics/",
            json={
                "network_ids": [network_id],
                "statistic": statistic,
                "parameters": parameters,
            },
            cookies=cookies,
        )
        queued.raise_for_status()
        task_id = queued.json()["task_id"]

        for _ in range(self.poll_max_attempts):
            poll = await self._http.get(
                f"/api/v1/tasks/status/{task_id}",
                cookies=cookies,
            )
            poll.raise_for_status()
            status = poll.json()
            state = status.get("state")
            if state == "SUCCESS":
                inner = status.get("result") or {}
                return self._post_process(network_id, statistic, inner.get("data"))
            if state == "FAILURE":
                err = status.get("error") or "task failed"
                return ToolResult(payload=None, is_error=True, error=err)
            if self.poll_interval_seconds > 0:
                await asyncio.sleep(self.poll_interval_seconds)

        msg = f"task {task_id} polling timed out"
        return ToolResult(payload=None, is_error=True, error=msg)

    def _post_process(self, network_id: str, statistic: str, raw: object) -> ToolResult:
        columns, rows = _to_table(raw)
        warnings: list[str] = []
        if not rows and statistic in _REQUIRES_OPTIMISATION:
            warnings.append("network_not_solved")

        units = _UNITS.get(statistic, "unknown")
        suffix = ", network_not_solved" if "network_not_solved" in warnings else ""
        summary_text = (
            f"{statistic} for network {network_id} — {len(rows)} entries{suffix}."
        )

        return ToolResult(
            payload={
                "summary": summary_text,
                "data": {"columns": columns, "rows": rows},
                "display_hint": "table",
                "network_id": network_id,
                "statistic": statistic,
                "units": units,
                "warnings": warnings,
            }
        )


def _to_table(raw: object) -> tuple[list[str], list[list[Any]]]:
    """Reshape ``serialize_df`` output into renderer-friendly columns+rows.

    DataFrame split-format -> ``["index", *columns]`` headers; rows prepended
    with the index value. Series flat dict -> ``["index", "value"]``.
    """
    if isinstance(raw, dict) and "index" in raw and "columns" in raw and "data" in raw:
        return (
            ["index", *list(raw["columns"])],
            [[idx, *row] for idx, row in zip(raw["index"], raw["data"], strict=False)],
        )
    if isinstance(raw, dict):
        return ["index", "value"], [[k, v] for k, v in raw.items()]
    return [], []
