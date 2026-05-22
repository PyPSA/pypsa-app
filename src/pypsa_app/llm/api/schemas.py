"""Pydantic request/response models for the chat API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatToolCall(BaseModel):
    """A tool call recorded on a prior assistant message.

    Mirrors the frontend ``ToolCall`` shape but only carries the fields
    the backend needs to reconstruct OpenAI ``tool_calls`` on the next
    turn (id, name, args). Streaming-state fields (``args_partial``,
    ``status``) are intentionally not modelled here.
    """

    id: str
    name: str
    args: dict[str, Any] | None = None


class ChatToolResult(BaseModel):
    """A tool result attached to a prior assistant message.

    The backend turns each of these into a ``role: "tool"`` message
    in the OpenAI message array so the model sees prior tool output
    on subsequent turns.
    """

    tool_call_id: str
    result: Any | None = None
    is_error: bool = False
    error: str | None = None


class ChatMessage(BaseModel):
    """A single message in a chat conversation.

    Mirrors the frontend Message / AssistantMessage shape so the wire
    format stays stable even if backend persistence is added later.
    Assistant messages carry ``tool_calls`` and ``tool_results`` arrays
    when prior turns invoked tools — the backend expands them into
    OpenAI tool/tool-message pairs before sending to the provider.
    """

    id: str
    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_calls: list[ChatToolCall] | None = None
    tool_results: list[ChatToolResult] | None = None
    timestamp: str  # ISO-8601, advisory only — server reorders by array index


class ChatContext(BaseModel):
    """Context the frontend injects so the LLM knows what the user is looking at.

    ``active_network_id`` / ``active_network_name`` carry the network the
    user is currently viewing — informational only, never used to bind
    ambiguous references to a network. ``previous_active_network_*`` are
    populated only on the turn where the active network changed since
    the previous message, so the model can be told about the switch.
    """

    active_network_id: str | None = None
    active_network_name: str | None = None
    previous_active_network_id: str | None = None
    previous_active_network_name: str | None = None


class ChatRequest(BaseModel):
    """Body of ``POST /api/v1/chat/stream``."""

    messages: list[ChatMessage]
    context: ChatContext = Field(default_factory=ChatContext)
