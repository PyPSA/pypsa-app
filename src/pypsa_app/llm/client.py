"""Async wrapper around the LLM provider (LiteLLM)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import litellm

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pypsa_app.llm.settings import LLMSettings

# Silently ignore provider-specific kwargs that LiteLLM does not recognise.
litellm.drop_params = True


def extract_reasoning(delta: object) -> str:
    """Normalise reasoning content across providers.

    Different providers expose reasoning / thinking content under
    different attribute names on the delta object:

    * Anthropic   → ``delta.thinking``
    * Ollama qwen → ``delta.reasoning_content``
    * OpenAI o1   → folded into content; not separately streamed

    Args:
        delta: A LiteLLM delta object (typically
            ``chunk.choices[0].delta``).

    Returns:
        The reasoning string, or ``""`` if neither field is present.
    """
    return (
        getattr(delta, "thinking", None)
        or getattr(delta, "reasoning_content", None)
        or ""
    )


def extract_text(delta: object) -> str:
    """Extract the plain-text content from a streaming delta.

    Args:
        delta: A LiteLLM delta object (typically
            ``chunk.choices[0].delta``).

    Returns:
        The text content string, or ``""`` if the ``content``
        attribute is absent or empty.
    """
    return getattr(delta, "content", None) or ""


class LLMClient:
    """Async LiteLLM wrapper that routes completions through the configured provider.

    Ollama models must use the ``openai/`` prefix: LiteLLM's ``ollama/`` adapter
    drops ``tool_calls`` for reasoning models.
    """

    def __init__(self, settings: LLMSettings) -> None:
        self._s = settings

    async def stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[Any]:  # noqa: ANN401 — litellm chunks are opaque to callers
        """Stream completion chunks from the configured LLM provider.

        Args:
            messages: Conversation history in OpenAI chat format.
            tools: Optional list of OpenAI tool definitions.

        Yields:
            Raw LiteLLM ``ModelResponse`` chunks as returned by the provider.
        """
        kwargs: dict[str, Any] = {
            "model": self._s.model_string,
            "messages": messages,
            "max_tokens": self._s.llm_max_tokens,
            "temperature": self._s.llm_temperature,
            "stream": True,
            "timeout": self._s.llm_request_timeout_seconds,
        }
        if self._s.llm_api_key:
            kwargs["api_key"] = self._s.llm_api_key
        if self._s.llm_api_base:
            kwargs["api_base"] = self._s.llm_api_base
        if tools:
            kwargs["tools"] = tools
        if self._s.llm_reasoning_effort is not None:
            kwargs["reasoning_effort"] = self._s.llm_reasoning_effort

        stream = await litellm.acompletion(**kwargs)
        async for chunk in stream:
            yield chunk

    async def health(self) -> dict[str, object]:
        """Ping the LLM provider with a 1-token completion.

        Returns:
            ``{"ok": True, "model": self._s.model_string}`` on success.

        Raises:
            Any exception from the provider (connection, auth, rate-limit,
            timeout, etc.) bubbles to the caller.
        """
        kwargs: dict[str, object] = {
            "model": self._s.model_string,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        if self._s.llm_api_key:
            kwargs["api_key"] = self._s.llm_api_key
        if self._s.llm_api_base:
            kwargs["api_base"] = self._s.llm_api_base
        await litellm.acompletion(**kwargs)
        return {"ok": True, "model": self._s.model_string}
