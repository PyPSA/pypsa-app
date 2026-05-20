"""Authentication routes"""

import logging

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_current_user_optional, get_db
from pypsa_app.backend.auth.password import verify_demo_credentials
from pypsa_app.backend.auth.providers import (
    OAUTH_PROVIDERS,
    get_oauth_client,
    login_or_register_oauth_user,
)
from pypsa_app.backend.auth.session import attach_session_cookie, get_session_store
from pypsa_app.backend.models import User, UserRole
from pypsa_app.backend.ratelimit import limiter
from pypsa_app.backend.schemas.auth import (
    AuthProviderInfo,
    AuthProvidersResponse,
    UserResponse,
)
from pypsa_app.backend.services.email import send_new_user_pending_email
from pypsa_app.backend.settings import SESSION_COOKIE_NAME, settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_admin_emails(db: Session) -> list[str]:
    """Get email addresses of all admin users."""
    return [
        a.email
        for a in db.scalars(
            select(User).where(User.role == UserRole.ADMIN, User.email.isnot(None))
        )
        if a.email
    ]


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


@router.get("/providers", response_model=AuthProvidersResponse)
async def get_auth_providers() -> AuthProvidersResponse:
    items: list[AuthProviderInfo] = []
    for pid in settings.enabled_oauth_providers:
        spec = OAUTH_PROVIDERS[pid]
        items.append(
            AuthProviderInfo(
                id=spec.id,
                name=spec.display_name,
                type="oauth",
                login_url=f"/api/v1/auth/login/{spec.id}",
                icon=spec.icon,
            )
        )
    if settings.auth_password_enabled:
        items.append(
            AuthProviderInfo(id="password", name="Password", type="credentials")
        )
    return AuthProvidersResponse(providers=items)


@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request) -> RedirectResponse:
    if provider not in settings.enabled_oauth_providers:
        raise HTTPException(
            status_code=404, detail=f"OAuth provider '{provider}' not enabled"
        )
    client = get_oauth_client(settings, provider)
    callback_url = f"{settings.base_url}/api/v1/auth/login/{provider}/callback"
    return await client.authorize_redirect(request, callback_url)


@router.get("/login/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if provider not in settings.enabled_oauth_providers:
        raise HTTPException(
            status_code=404, detail=f"OAuth provider '{provider}' not enabled"
        )
    spec = OAUTH_PROVIDERS[provider]
    client = get_oauth_client(settings, provider)

    try:
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning("OAuth error (possible CSRF): %s, client_ip=%s", e, client_ip)
        raise HTTPException(status_code=400, detail="Authentication failed") from e

    try:
        canonical = await spec.fetch_user(client, token)
        user = login_or_register_oauth_user(db, provider=provider, canonical=canonical)
        is_pending = user.role == UserRole.PENDING
        admin_emails = _get_admin_emails(db) if is_pending else []

        db.commit()
        db.refresh(user)

        redirect_url = settings.base_url
        if is_pending:
            redirect_url = f"{settings.base_url}/pending-approval"
            background_tasks.add_task(
                send_new_user_pending_email, admin_emails, user.username
            )

        response = RedirectResponse(url=redirect_url)
        return attach_session_cookie(
            response, user.id, base_url=settings.base_url, ttl=settings.session_ttl
        )
    except Exception as e:
        logger.exception("OAuth callback error")
        raise HTTPException(status_code=500, detail="Authentication failed") from e


@router.post("/login/password")
@limiter.limit(settings.ratelimit_login)
async def password_login(
    request: Request,
    body: PasswordLoginRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not settings.auth_password_enabled:
        raise HTTPException(status_code=400, detail="Password login not available")

    user = verify_demo_credentials(body.email, body.password, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response = JSONResponse(content={"ok": True})
    return attach_session_cookie(
        response, user.id, base_url=settings.base_url, ttl=settings.session_ttl
    )


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Authentication is disabled")

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        get_session_store().delete_session(session_id)

    response = RedirectResponse(url=f"{settings.base_url}/login", status_code=303)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Authentication is disabled")
    if user is None:
        raise HTTPException(
            status_code=401, detail="Authentication required. Please log in."
        )

    return user
