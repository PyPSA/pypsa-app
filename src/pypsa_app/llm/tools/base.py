"""Base interface for LLM tool definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


@dataclass(slots=True, frozen=True)
class ToolContext:
    """Immutable context passed to every tool invocation.

    Carries the authenticated user's identity and a session cookie
    that tools forward to internal HTTP calls so existing auth checks apply.
    """

    user_id: str
    auth_cookie: str | None


@dataclass(slots=True, frozen=True)
class ToolResult:
    """Return value of a tool invocation — success or failure."""

    payload: dict[str, Any] | None
    is_error: bool = False
    error: str | None = None


class Tool(ABC):
    """Abstract tool that the LLM can invoke.

    Subclasses must set ``name``, ``description``, and ``parameters_schema``
    as class-level attributes and implement :meth:`invoke`.
    """

    name: str
    description: str
    parameters_schema: dict[str, Any]

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    @abstractmethod
    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute the tool with the given arguments and context."""

    def to_openai(self) -> dict[str, Any]:
        """Return an OpenAI-compatible function-tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
