"""Core chat orchestration: combines LLM calls with tool execution."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

import httpx
import litellm.exceptions

from pypsa_app.llm.client import extract_reasoning, extract_text
from pypsa_app.llm.prompts import build_system_prompt
from pypsa_app.llm.events import (
    ReasoningMessageContent,
    RunError,
    RunFinished,
    RunStarted,
    TextMessageContent,
    ToolCallArgs,
    ToolCallEnd,
    ToolCallResult,
    ToolCallStart,
    Usage,
    to_sse,
)
from pypsa_app.llm.tools.base import ToolContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pypsa_app.backend.models import User
    from pypsa_app.llm.api.schemas import ChatContext, ChatMessage
    from pypsa_app.llm.client import LLMClient
    from pypsa_app.llm.settings import LLMSettings
    from pypsa_app.llm.tools import ToolRegistry

logger = logging.getLogger(__name__)

_DISCONNECT_MSG = "client disconnected"


def _process_delta(
    delta: Any,  # noqa: ANN401 — LLM SDK dynamic object
    index_buffers: dict[int, dict[str, str]],
    message_id: str,
) -> list[bytes]:
    """Process a single stream chunk delta, returning SSE bytes.

    Handles tool-call delta buffering (ToolCallStart / ToolCallArgs),
    text content (TextMessageContent), and reasoning content
    (ReasoningMessageContent) for one chunk.
    """
    events: list[bytes] = []

    # ── tool-call deltas ──────────────────────────
    tool_calls = getattr(delta, "tool_calls", None) or []
    for tc_delta in tool_calls:
        tc_index = getattr(tc_delta, "index", 0)
        tc_id = getattr(tc_delta, "id", None)
        tc_fn = getattr(tc_delta, "function", None)
        tc_args = getattr(tc_fn, "arguments", "") if tc_fn else ""
        tc_name = getattr(tc_fn, "name", None) if tc_fn else None

        # First appearance: buffer and emit ToolCallStart
        if tc_index not in index_buffers:
            resolved_id = tc_id or f"call_{tc_index}"
            resolved_name = tc_name or "unknown"
            index_buffers[tc_index] = {
                "id": resolved_id,
                "name": resolved_name,
                "args_str": "",
            }
            events.append(
                to_sse(
                    ToolCallStart(
                        tool_call_id=resolved_id,
                        tool_name=resolved_name,
                    )
                )
            )

        buf = index_buffers[tc_index]
        if tc_args:
            buf["args_str"] += tc_args
            events.append(
                to_sse(
                    ToolCallArgs(
                        tool_call_id=buf["id"],
                        delta=tc_args,
                    )
                )
            )

    # ── text deltas ───────────────────────────────
    text: str = extract_text(delta)
    if text:
        events.append(
            to_sse(
                TextMessageContent(
                    message_id=message_id, delta=text
                )
            )
        )

    # ── reasoning deltas ──────────────────────────
    reasoning: str = extract_reasoning(delta)
    if reasoning:
        events.append(
            to_sse(
                ReasoningMessageContent(
                    message_id=message_id, delta=reasoning
                )
            )
        )

    return events


def _expand_messages(messages: list[ChatMessage]) -> list[dict[str, object]]:
    """Convert ChatMessage entries to OpenAI-format messages.

    User messages pass through unchanged. Assistant messages with
    ``tool_calls`` are emitted with an OpenAI ``tool_calls`` array;
    each entry in ``tool_results`` becomes a separate ``role: "tool"``
    message immediately after, so the model sees both what it called
    and what came back when continuing a multi-turn conversation.
    """
    expanded: list[dict[str, object]] = []
    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            tool_calls_payload = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.args or {}),
                    },
                }
                for tc in m.tool_calls
            ]
            expanded.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": tool_calls_payload,
                }
            )
            for tr in m.tool_results or []:
                expanded.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.tool_call_id,
                        "content": json.dumps(
                            tr.result if not tr.is_error else {"error": tr.error}
                        ),
                    }
                )
            continue
        expanded.append({"role": m.role, "content": m.content})
    return expanded


def _cancel_on_disconnect(run_id: str) -> None:
    """Raise CancelledError when the client has disconnected.

    Cancellation must NOT emit RunError or RunFinished — the stream
    simply ends.
    """
    logger.info(
        "chat stream cancelled",
        extra={"run_id": run_id, "reason": "client_disconnect"},
    )
    raise asyncio.CancelledError(_DISCONNECT_MSG) from None


class ChatService:
    """Orchestrates a chat turn: streams LLM deltas and invokes tools.

    Emits ``RunStarted``, streams ``TextMessageContent`` deltas, detects
    and streams tool calls (``ToolCallStart``, ``ToolCallArgs``,
    ``ToolCallEnd``, ``ToolCallResult``), and finishes with
    ``RunFinished``.
    """

    def __init__(
        self,
        *,
        client: LLMClient,
        tools: ToolRegistry,
        settings: LLMSettings,
    ) -> None:
        self._client = client
        self._tools = tools
        self._settings = settings

    async def run_chat(
        self,
        *,
        user: User,
        messages: list[ChatMessage],
        context: ChatContext,
        client_disconnected: Any,  # noqa: ANN401 — async callable protocol
        auth_cookie: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Execute a chat turn, emitting AG-UI SSE events.

        Streams text content deltas and tool-call events between
        ``RunStarted`` and ``RunFinished`` bookend events. Supports up to
        ``llm_max_tool_iterations`` tool-call round-trips.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        model = self._settings.model_string

        logger.info(
            "chat run started",
            extra={"run_id": run_id, "user_id": user.id, "model": model},
        )

        yield to_sse(RunStarted(run_id=run_id, model=model))

        openai_messages: list[dict[str, object]] = [
            {"role": "system", "content": build_system_prompt(context)},
            *_expand_messages(messages),
        ]

        tool_ctx = ToolContext(user_id=str(user.id), auth_cookie=auth_cookie)
        tool_schemas = self._tools.schemas()
        max_iterations = self._settings.llm_max_tool_iterations

        for _iteration in range(max_iterations):
            message_id = f"msg_{uuid.uuid4().hex[:12]}"
            index_buffers: dict[int, dict[str, str]] = {}
            finish_reason: str | None = None

            try:
                async for chunk in self._client.stream(
                    openai_messages, tools=tool_schemas
                ):
                    delta = chunk.choices[0].delta
                    finish_reason = getattr(
                        chunk.choices[0], "finish_reason", None
                    )

                    for sse_bytes in _process_delta(
                        delta, index_buffers, message_id
                    ):
                        yield sse_bytes

                    # ── client-disconnect check ───────────
                    disconnected = client_disconnected()
                    if asyncio.iscoroutine(disconnected):
                        disconnected = await disconnected
                    if disconnected:
                        _cancel_on_disconnect(run_id)
            except Exception as exc:
                code, log_msg, is_critical = self._provider_error_code(
                    exc
                )
                if is_critical:
                    logger.exception(
                        log_msg,
                        extra={"run_id": run_id, "error_code": code},
                    )
                else:
                    logger.warning(
                        log_msg,
                        extra={"run_id": run_id, "error": str(exc)},
                    )
                yield to_sse(
                    RunError(run_id=run_id, code=code, message=str(exc))
                )
                return

            if finish_reason == "tool_calls":
                async for evt_bytes in self._finish_tool_calls(
                    index_buffers, tool_ctx, openai_messages
                ):
                    yield evt_bytes
                continue

            yield to_sse(
                RunFinished(
                    run_id=run_id,
                    usage=Usage(input_tokens=0, output_tokens=0),
                    stop_reason=finish_reason or "end_turn",
                )
            )
            return

        # Loop exhausted — soft-stop: tell the model to wrap up without
        # tools and stream a final summary so the user gets a coherent
        # response instead of an error mid-stream.
        logger.warning(
            "tool iteration limit reached — soft-stopping with summary",
            extra={"run_id": run_id, "iterations": max_iterations},
        )
        openai_messages.append(
            {
                "role": "user",
                "content": (
                    f"[System notice] You have reached the maximum of "
                    f"{max_iterations} tool calls for this turn. Stop "
                    f"calling tools now. Summarise for the user what you "
                    f"have found so far, describe what remains unexamined, "
                    f"and tell them they can reply 'continue' if they want "
                    f"you to keep exploring."
                ),
            }
        )
        async for evt_bytes in self._stream_summary(
            run_id, openai_messages
        ):
            yield evt_bytes

    async def health(self) -> dict[str, object]:
        """Cheap readiness check — pings the LLM provider."""
        return await self._client.health()

    @staticmethod
    def _provider_error_code(exc: Exception) -> tuple[str, str, bool]:
        """Map a provider exception to (code, log_message, is_critical).

        - httpx.TimeoutException → "provider_timeout"
        - litellm.AuthenticationError → "provider_auth_failed"
        - litellm.RateLimitError → "provider_rate_limit"
        - anything else → "internal"
        """
        if isinstance(exc, httpx.TimeoutException):
            return ("provider_timeout", "provider timeout", False)
        if isinstance(exc, litellm.exceptions.AuthenticationError):
            return ("provider_auth_failed", "provider auth failed", False)
        if isinstance(exc, litellm.exceptions.RateLimitError):
            return ("provider_rate_limit", "provider rate limit", False)
        return ("internal", "chat run failed", True)

    async def _stream_summary(
        self,
        run_id: str,
        openai_messages: list[dict[str, object]],
    ) -> AsyncIterator[bytes]:
        """Stream a tools-disabled summary call and emit RunFinished.

        Used by the soft-stop path when the tool-iteration cap is hit:
        the model gets one final pass with no tools to wrap up the
        conversation cleanly. Errors here surface as RunError(internal)
        rather than crashing the stream.
        """
        summary_message_id = f"msg_{uuid.uuid4().hex[:12]}"
        try:
            async for chunk in self._client.stream(openai_messages, tools=None):
                delta = chunk.choices[0].delta
                text = extract_text(delta)
                if text:
                    yield to_sse(
                        TextMessageContent(
                            message_id=summary_message_id, delta=text
                        )
                    )
                reasoning = extract_reasoning(delta)
                if reasoning:
                    yield to_sse(
                        ReasoningMessageContent(
                            message_id=summary_message_id, delta=reasoning
                        )
                    )
        except Exception as exc:
            code, log_msg, is_critical = self._provider_error_code(exc)
            if is_critical:
                logger.exception(
                    log_msg, extra={"run_id": run_id, "error_code": code}
                )
            else:
                logger.warning(
                    log_msg, extra={"run_id": run_id, "error": str(exc)}
                )
            yield to_sse(
                RunError(run_id=run_id, code=code, message=str(exc))
            )
            return

        yield to_sse(
            RunFinished(
                run_id=run_id,
                usage=Usage(input_tokens=0, output_tokens=0),
                stop_reason="tool_iteration_limit",
            )
        )

    async def _finish_tool_calls(
        self,
        index_buffers: dict[int, dict[str, str]],
        tool_ctx: ToolContext,
        openai_messages: list[dict[str, object]],
    ) -> AsyncIterator[bytes]:
        """Handle ``finish_reason == "tool_calls"``.

        Emits ``ToolCallEnd`` and ``ToolCallResult`` for each buffered
        tool call, then appends the assistant and tool messages to
        ``openai_messages`` for the next iteration.
        """
        tool_msg_parts: list[dict[str, object]] = []
        tool_responses: list[dict[str, object]] = []
        for buf in index_buffers.values():
            tcid = buf["id"]
            args_str = buf["args_str"]

            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError as e:
                msg = f"invalid json: {e}"
                yield to_sse(
                    ToolCallResult(
                        tool_call_id=tcid,
                        result=None,
                        is_error=True,
                        error=msg,
                    )
                )
                tool_msg_parts.append(
                    {
                        "id": tcid,
                        "type": "function",
                        "function": {
                            "name": buf["name"],
                            "arguments": args_str,
                        },
                    }
                )
                tool_responses.append(
                    {
                        "role": "tool",
                        "tool_call_id": tcid,
                        "content": json.dumps({"error": msg}),
                    }
                )
                continue

            yield to_sse(ToolCallEnd(tool_call_id=tcid, args=args))

            tool_result = await self._tools.invoke(
                buf["name"], args, tool_ctx
            )
            yield to_sse(
                ToolCallResult(
                    tool_call_id=tcid,
                    result=tool_result.payload,
                    is_error=tool_result.is_error,
                    error=tool_result.error,
                )
            )

            tool_msg_parts.append(
                {
                    "id": tcid,
                    "type": "function",
                    "function": {
                        "name": buf["name"],
                        "arguments": args_str,
                    },
                }
            )
            tool_responses.append(
                {
                    "role": "tool",
                    "tool_call_id": tcid,
                    "content": json.dumps(tool_result.payload),
                }
            )

        openai_messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": tool_msg_parts,
            }
        )
        openai_messages.extend(tool_responses)
