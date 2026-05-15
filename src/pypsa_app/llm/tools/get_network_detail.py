"""Tool: structured summary of a single network.

Returns a *curated* payload (component counts, dimensions, carriers,
countries, file size, ownership, plus a small ``meta_summary`` listing
top-level meta keys and serialized size) — never the full ``meta`` blob,
which on real PyPSA-Eur networks is tens of KB of nested config and
otherwise blows the model's context window.
"""

from __future__ import annotations

import json
from typing import Any

from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult
from pypsa_app.llm.tools.http_client import cookies_for


def _carrier_names(facets: dict[str, Any] | None) -> list[str]:
    carriers = (facets or {}).get("carriers") or {}
    return sorted(carriers.keys()) if isinstance(carriers, dict) else []


def _countries(facets: dict[str, Any] | None) -> list[str]:
    countries = (facets or {}).get("countries") or []
    return list(countries) if isinstance(countries, list) else []


def _meta_summary(meta: dict[str, Any] | None) -> dict[str, Any]:
    meta = meta or {}
    return {
        "size_bytes": len(json.dumps(meta, default=str)),
        "keys": sorted(meta.keys()) if isinstance(meta, dict) else [],
    }


def _last_updated_at(history: list[Any] | None) -> str | None:
    return history[-1] if history else None


class GetNetworkDetailTool(Tool):
    """Structured summary of one network the current user can see."""

    name = "get_network_detail"
    description = (
        "Get a structured summary of a single PyPSA energy network. "
        "Returns id, name, filename, created_at, last_updated_at, "
        "visibility, owner, file_size_bytes, dimensions_count "
        "(timesteps/periods/scenarios), per-component counts (Bus, "
        "Generator, Line, ...), carriers and countries present, plus a "
        "small meta_summary listing the top-level meta keys and the meta "
        "blob size in bytes. The full meta dictionary is intentionally "
        "NOT returned — it can be tens of KB of run config on real "
        "PyPSA-Eur networks. Use list_networks first to discover ids."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "network_id": {
                "type": "string",
                "description": "UUID of the network. Get ids from list_networks.",
            },
        },
        "required": ["network_id"],
    }

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        network_id = args["network_id"]
        r = await self._http.get(
            f"/api/v1/networks/{network_id}",
            cookies=cookies_for(ctx),
        )
        r.raise_for_status()
        body: dict[str, Any] = r.json()

        owner = body.get("owner") or {}
        is_owner = owner.get("id") == ctx.user_id
        name = body.get("name") or body.get("filename", "unnamed")

        slim = {
            "id": body.get("id"),
            "name": name,
            "filename": body.get("filename"),
            "created_at": body.get("created_at"),
            "last_updated_at": _last_updated_at(body.get("update_history")),
            "visibility": body.get("visibility"),
            "is_owner": is_owner,
            "source_run_id": body.get("source_run_id"),
            "file_size_bytes": body.get("file_size"),
            "dimensions_count": body.get("dimensions_count") or {},
            "components_count": body.get("components_count") or {},
            "carriers": _carrier_names(body.get("facets")),
            "countries": _countries(body.get("facets")),
            "meta_summary": _meta_summary(body.get("meta")),
        }

        components = slim["components_count"]
        component_summary = ", ".join(
            f"{k}={v}" for k, v in list(components.items())[:6]
        )
        ownership = "owned by you" if is_owner else "owned by another user"
        summary = (
            f"Network '{name}' (id: {network_id}), file '{slim['filename']}', "
            f"{ownership}, components: {component_summary}."
        )

        return ToolResult(
            payload={
                "summary": summary,
                "data": {"network": slim},
            }
        )
