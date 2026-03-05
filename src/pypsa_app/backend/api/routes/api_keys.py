"""API key management routes."""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, hash_api_key, require_permission
from pypsa_app.backend.models import ApiKey, Permission, User, UserRole
from pypsa_app.backend.schemas.api_key import ApiKeyCreate, ApiKeyResponse

router = APIRouter()


@router.post("/", response_model=ApiKeyResponse)
def create_api_key(
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> ApiKeyResponse:
    # Validate linked user exists and is a bot
    bot_user = db.query(User).filter(User.id == body.user_id).first()
    if not bot_user:
        raise HTTPException(404, "User not found")
    if bot_user.role != UserRole.BOT:
        raise HTTPException(400, "API keys can only be linked to bot users")

    raw_key = secrets.token_urlsafe(32)
    key_hash = hash_api_key(raw_key)

    expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)

    api_key = ApiKey(
        name=body.name,
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        user_id=body.user_id,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    response = ApiKeyResponse.model_validate(api_key)
    response.key = raw_key
    return response


@router.get("/", response_model=list[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> list[ApiKeyResponse]:
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


@router.delete("/{key_id}", status_code=204)
def delete_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> None:
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(404, "API key not found")

    db.delete(api_key)
    db.commit()
