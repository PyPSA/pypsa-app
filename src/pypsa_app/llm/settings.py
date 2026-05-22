"""LLM provider and generation configuration loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM configuration sourced from environment variables.

    Env vars are read with their exact upstream names (no prefix).
    """

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    llm_provider: str = Field(
        default="openai",
        alias="LLM_PROVIDER",
        description="LLM provider name",
    )
    llm_model: str = Field(
        default="qwen3.5:9b",
        alias="LLM_MODEL",
        description="LLM model identifier",
    )
    llm_api_key: str = Field(
        default="",
        alias="LLM_API_KEY",
        description="API key for the configured provider",
    )
    llm_api_base: str | None = Field(
        default=None,
        alias="LLM_API_BASE",
        description="Custom API base URL (optional)",
    )
    llm_internal_api_base: str | None = Field(
        default=None,
        alias="LLM_INTERNAL_API_BASE",
        description="Base URL for internal HTTP calls to the app's own REST API",
    )
    llm_internal_port: int = Field(
        default=8000,
        alias="LLM_INTERNAL_PORT",
        description="Port used when llm_internal_api_base is not set explicitly",
    )

    # Generation parameters
    llm_max_tokens: int = Field(
        default=2048,
        alias="LLM_MAX_TOKENS",
        description="Maximum tokens per completion",
    )
    llm_temperature: float = Field(
        default=0.2,
        alias="LLM_TEMPERATURE",
        description="Sampling temperature",
    )
    llm_request_timeout_seconds: float = Field(
        default=120.0,
        alias="LLM_REQUEST_TIMEOUT_SECONDS",
        description="Timeout in seconds for provider requests",
    )
    llm_reasoning_effort: str | None = Field(
        default=None,
        alias="LLM_REASONING_EFFORT",
        description=(
            "Reasoning effort for OpenAI-compatible reasoning models. "
            "One of None (default, let provider decide), 'low', 'medium', 'high'. "
            "Passed through as 'reasoning_effort' to the provider; LiteLLM's "
            "drop_params=True means providers that don't support it just "
            "ignore it."
        ),
    )

    # Feature flag and tool execution limits
    chat_enabled: bool = Field(
        default=False,
        alias="CHAT_ENABLED",
        description="Feature flag to enable chat endpoints",
    )
    llm_max_tool_iterations: int = Field(
        default=8,
        alias="LLM_MAX_TOOL_ITERATIONS",
        description="Maximum tool-calling loop iterations per chat request",
    )

    @property
    def resolved_internal_api_base(self) -> str:
        """The base URL for internal HTTP calls.

        Returns ``llm_internal_api_base`` when explicitly set; otherwise
        defaults to ``http://127.0.0.1:{llm_internal_port}``.
        """
        if self.llm_internal_api_base is not None:
            return self.llm_internal_api_base
        return f"http://127.0.0.1:{self.llm_internal_port}"

    @property
    def model_string(self) -> str:
        """LiteLLM-style model identifier combining provider and model.

        Returns ``{provider}/{model}``. For Ollama models, use the
        ``openai/`` provider prefix — **not** ``ollama/`` — because the
        ``ollama/`` prefix drops ``tool_calls`` for reasoning models.
        """
        return f"{self.llm_provider}/{self.llm_model}"
