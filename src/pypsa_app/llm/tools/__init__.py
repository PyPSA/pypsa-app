"""Tool registry — register, invoke, and tool-schema export."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult
from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool
from pypsa_app.llm.tools.get_network_statistics import GetNetworkStatisticsTool
from pypsa_app.llm.tools.list_networks import ListNetworksTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Holds registered :class:`Tool` instances and dispatches invocations by name.

    Construct with a list of concrete tool instances.  The registry indexes
    them by :attr:`Tool.name` so that lookups during a chat turn are O(1).
    """

    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI‑compatible function‑tool schemas for every registered tool."""
        return [t.to_openai() for t in self._tools.values()]

    async def invoke(
        self, name: str, args: dict[str, Any], ctx: ToolContext
    ) -> ToolResult:
        """Look up *name* and delegate to :meth:`Tool.invoke`.

        Returns:
            A :class:`ToolResult` — on success from the tool itself; on
            failure a synthetic error result so the stream never crashes.
        """
        tool = self._tools.get(name)
        if tool is None:
            msg = f"unknown tool: {name}"
            return ToolResult(payload=None, is_error=True, error=msg)

        try:
            return await tool.invoke(args, ctx)
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                payload=None,
                is_error=True,
                error=f"http {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:  # noqa: BLE001 — surface to LLM, never crash the stream
            logger.warning(
                "tool execution error",
                extra={"tool": name, "error": str(exc)},
            )
            return ToolResult(
                payload=None,
                is_error=True,
                error=str(exc),
            )


def build_default_registry(http: httpx.AsyncClient) -> ToolRegistry:
    """Build a :class:`ToolRegistry` populated with all default tools."""
    return ToolRegistry([
        ListNetworksTool(http),
        GetNetworkDetailTool(http),
        GetNetworkStatisticsTool(http),
    ])
