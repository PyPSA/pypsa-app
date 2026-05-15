"""Version information endpoints"""

import pypsa
from fastapi import APIRouter

from pypsa_app.backend.__version__ import __version__
from pypsa_app.backend.schemas.version import VersionResponse
from pypsa_app.backend.settings import settings

router = APIRouter()


@router.get("/", response_model=VersionResponse)
async def get_version() -> dict:
    """Get PyPSA and application version information"""
    return {
        "version": __version__,
        "pypsa_version": pypsa.__version__,
        "local_mode": settings.local_mode,
        "runs_enabled": bool(settings.resolved_backends),
        "chat_enabled": settings.llm.chat_enabled,
    }
