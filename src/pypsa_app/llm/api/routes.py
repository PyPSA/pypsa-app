"""FastAPI router for the /api/v1/chat endpoints."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from pypsa_app.backend.api.deps import get_active_user
from pypsa_app.backend.models import User
from pypsa_app.backend.settings import SESSION_COOKIE_NAME
from pypsa_app.llm.api.deps import get_chat_service, require_chat_enabled
from pypsa_app.llm.api.schemas import ChatRequest
from pypsa_app.llm.service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/chat/stream",
    dependencies=[Depends(require_chat_enabled)],
    response_class=StreamingResponse,
)
async def chat_stream(
    body: ChatRequest,
    request: Request,
    user: Annotated[User, Depends(get_active_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    sse_headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }

    async def stream() -> AsyncIterator[bytes]:
        auth_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        try:
            async for sse_bytes in service.run_chat(
                user=user,
                messages=body.messages,
                context=body.context,
                client_disconnected=request.is_disconnected,
                auth_cookie=auth_cookie,
            ):
                yield sse_bytes
                if await request.is_disconnected():
                    logger.info(
                        "chat stream cancelled",
                        extra={
                            "user_id": user.id,
                            "reason": "client_disconnect",
                        },
                    )
                    return
        except asyncio.CancelledError:
            logger.info(
                "chat stream cancelled",
                extra={
                    "user_id": user.id,
                    "reason": "client_disconnect",
                },
            )
            raise

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers=sse_headers,
    )


@router.get(
    "/chat/health",
    dependencies=[Depends(require_chat_enabled)],
)
async def chat_health(
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict[str, object]:
    """Cheap readiness check — pings the LLM provider with a 1-token completion."""
    return await service.health()
