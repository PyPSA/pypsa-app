"""FastAPI dependency providers for the chat API routes."""

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status

from pypsa_app.backend.api.deps import get_settings
from pypsa_app.backend.settings import Settings
from pypsa_app.llm.client import LLMClient
from pypsa_app.llm.service import ChatService
from pypsa_app.llm.tools import ToolRegistry, build_default_registry
from pypsa_app.llm.tools.http_client import build_internal_http_client


def require_chat_enabled(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not settings.llm.chat_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="chat is disabled",
        )


def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMClient:
    """Return an :class:`LLMClient` configured from the application settings."""
    return LLMClient(settings.llm)


def get_internal_http_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> httpx.AsyncClient:
    """Return an :class:`httpx.AsyncClient` pointed at the app's own REST API."""
    return build_internal_http_client(settings)


def get_tool_registry(
    http: Annotated[httpx.AsyncClient, Depends(get_internal_http_client)],
) -> ToolRegistry:
    """Return a :class:`ToolRegistry` populated with all default tools."""
    return build_default_registry(http)


def get_chat_service(
    client: Annotated[LLMClient, Depends(get_llm_client)],
    registry: Annotated[ToolRegistry, Depends(get_tool_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatService:
    """Return a fully wired :class:`ChatService`."""
    return ChatService(
        client=client,
        tools=registry,
        settings=settings.llm,
    )
