"""Tool: list available networks visible to the current user, paginated."""

from __future__ import annotations

import logging
from typing import Any

from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult
from pypsa_app.llm.tools.http_client import cookies_for

logger = logging.getLogger(__name__)


def _last_updated(item: dict[str, Any]) -> str | None:
    history = item.get("update_history") or []
    if history:
        return history[-1]
    return item.get("created_at")


class ListNetworksTool(Tool):
    """List networks the user has access to, with pagination."""

    name = "list_networks"
    description = (
        "List PyPSA energy networks visible to the current user, with "
        "pagination. Returns each network's id, name, creation date, "
        "visibility, and whether the current user owns it. Networks "
        "marked is_owner=false are public networks owned by other "
        "users.\n\n"
        "Use when the user asks about their networks, wants an "
        "overview, or needs network ids before drilling in.\n\n"
        "Results are paginated. Default page size is 25, maximum 100. "
        "The response includes total, has_more, and next_offset. To "
        "see the next page, call again with offset=next_offset and the "
        "same sort_by and order. Sort by created_at (default) or name; "
        "order desc (default) or asc."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "offset": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Number of networks to skip (for pagination).",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 25,
                "description": "Maximum networks to return per page (1-100).",
            },
            "sort_by": {
                "type": "string",
                "enum": ["created_at", "name"],
                "default": "created_at",
                "description": "Field to sort by.",
            },
            "order": {
                "type": "string",
                "enum": ["asc", "desc"],
                "default": "desc",
                "description": "Sort direction.",
            },
        },
    }

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        limit = max(1, min(int(args.get("limit", 25)), 100))
        offset = max(0, int(args.get("offset", 0)))
        sort_by = args.get("sort_by", "created_at")
        order = args.get("order", "desc")
        r = await self._http.get(
            "/api/v1/networks/",
            params={
                "limit": limit,
                "skip": offset,
                "sort_by": sort_by,
                "order": order,
            },
            cookies=cookies_for(ctx),
        )
        r.raise_for_status()
        body = r.json()
        items = body.get("data", [])
        meta = body.get("meta") or {}
        total = int(meta.get("total", len(items)))

        user_id = ctx.user_id
        rows = [
            [
                n.get("id"),
                n.get("name") or n.get("filename", ""),
                n.get("visibility", "private"),
                (n.get("owner") or {}).get("id") == user_id,
                _last_updated(n),
            ]
            for n in items
        ]

        returned = len(rows)
        has_more = (offset + returned) < total
        next_offset = (offset + returned) if has_more else None

        more_hint = (
            f" {total - offset - returned} more available — "
            f"call again with offset={next_offset}."
            if has_more
            else ""
        )
        summary = (
            f"Found {returned} networks (showing {offset + 1}-"
            f"{offset + returned} of {total})." + more_hint
        )

        return ToolResult(
            payload={
                "summary": summary,
                "data": {
                    "columns": [
                        "id",
                        "name",
                        "visibility",
                        "is_owner",
                        "modified",
                    ],
                    "rows": rows,
                    "total": total,
                    "offset": offset,
                    "returned": returned,
                    "has_more": has_more,
                    "next_offset": next_offset,
                    "sort_by": sort_by,
                    "order": order,
                },
                "display_hint": "table",
            }
        )
