"""AG-UI event dataclasses and SSE serializer for chat streaming."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass(slots=True, frozen=True)
class Usage:
    """Token usage reported by the LLM provider."""

    input_tokens: int
    output_tokens: int


@dataclass(slots=True, frozen=True)
class RunStarted:
    """Emitted when a chat turn begins."""

    run_id: str
    model: str


@dataclass(slots=True, frozen=True)
class RunFinished:
    """Emitted when the assistant finishes responding."""

    run_id: str
    usage: Usage
    stop_reason: str


@dataclass(slots=True, frozen=True)
class RunError:
    """Emitted when an unrecoverable error occurs mid-run."""

    run_id: str
    code: str
    message: str


@dataclass(slots=True, frozen=True)
class TextMessageContent:
    """Streaming text-content delta from the assistant."""

    message_id: str
    delta: str


@dataclass(slots=True, frozen=True)
class ReasoningMessageContent:
    """Streaming reasoning-content delta from the assistant."""

    message_id: str
    delta: str


@dataclass(slots=True, frozen=True)
class ToolCallStart:
    """Emitted when the LLM decides to call a tool."""

    tool_call_id: str
    tool_name: str


@dataclass(slots=True, frozen=True)
class ToolCallArgs:
    """Streamed JSON-fragment of tool-call arguments."""

    tool_call_id: str
    delta: str


@dataclass(slots=True, frozen=True)
class ToolCallEnd:
    """All argument deltas received; tool about to execute."""

    tool_call_id: str
    args: Any = None  # noqa: ANN401 – arbitrary JSON payload


@dataclass(slots=True, frozen=True)
class ToolCallResult:
    """Emitted after a tool invocation completes or fails."""

    tool_call_id: str
    result: Any = None  # noqa: ANN401 – arbitrary JSON payload
    is_error: bool = False
    error: str | None = None

    def __post_init__(self) -> None:
        if self.is_error and self.error is None:
            msg = "error must be a non-None string when is_error is True"
            raise ValueError(msg)


RunEvent = (
    RunStarted
    | RunFinished
    | RunError
    | TextMessageContent
    | ReasoningMessageContent
    | ToolCallStart
    | ToolCallArgs
    | ToolCallEnd
    | ToolCallResult
)
"""Union of all event types accepted by :func:`sse_encode`."""


def to_sse(event: RunEvent) -> bytes:
    """Serialize an event dataclass to compact SSE wire-format bytes.

    Uses compact JSON (no spaces) for predictable downstream parsing.
    """
    event_name = type(event).__name__
    payload = json.dumps(asdict(event), separators=(",", ":"))
    return f"event: {event_name}\ndata: {payload}\n\n".encode()


_KEEPALIVE_BYTES = b":keepalive\n\n"


async def heartbeat(
    gen: AsyncIterator[bytes],
    *,
    interval: float = 15.0,
) -> AsyncIterator[bytes]:
    """Wrap an SSE byte generator with keepalive comment lines.

    If the wrapped generator does not yield for *interval* seconds,
    a ``:keepalive\\n\\n`` comment line is emitted to prevent proxies
    and load balancers from closing the connection.

    The underlying generator's ``__anext__()`` is never cancelled —
    heartbeats are sent while the generator is still awaiting its
    next item.
    """
    next_task: asyncio.Task[bytes] | None = None
    cancelled = False

    try:
        while not cancelled:
            if next_task is None:
                next_task = asyncio.ensure_future(gen.__anext__())

            sleep_task = asyncio.ensure_future(asyncio.sleep(interval))

            done, pending = await asyncio.wait(
                [next_task, sleep_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the sleep task (it's no longer needed).
            # Never cancel next_task — it holds the pending generator step.
            if sleep_task in pending:
                sleep_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sleep_task

            if next_task in done:
                try:
                    result = next_task.result()
                    yield result
                    next_task = None  # reset — next iteration fetches a new item
                except StopAsyncIteration:
                    return
                except asyncio.CancelledError:
                    return
            else:
                # Timer fired before the generator produced output
                yield _KEEPALIVE_BYTES
                # next_task is still pending — keep it for the next loop
    except asyncio.CancelledError:
        cancelled = True
        if next_task is not None and not next_task.done():
            next_task.cancel()
        raise
    finally:
        if next_task is not None and not next_task.done():
            next_task.cancel()
