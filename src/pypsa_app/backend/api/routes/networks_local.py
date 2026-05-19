"""LOCAL_MODE-only network routes. Mounted by main.py when settings.local_mode."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.models import Network, Permission, User
from pypsa_app.backend.schemas.network import (
    NetworkRegisterPathRequest,
    NetworkResponse,
)
from pypsa_app.backend.services.network import register_network_in_place

router = APIRouter()


@router.post("/register-path", response_model=NetworkResponse, status_code=201)
def register_network_by_path(
    body: NetworkRegisterPathRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> Network:
    """Register an existing .nc file at its absolute path without copying it.

    The path must be absolute and point to an existing .nc file.
    Calling twice with the same path returns the already-registered record.
    """
    raw = body.absolute_path.strip()
    if not raw:
        raise HTTPException(400, "absolute_path must not be empty")

    candidate = Path(raw)
    if not candidate.is_absolute():
        raise HTTPException(400, "Path must be absolute")

    try:
        network = register_network_in_place(candidate, user.id, db)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(400, f"Cannot access path: {exc}") from exc

    db.commit()
    db.refresh(network)
    return network
