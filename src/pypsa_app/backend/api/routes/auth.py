"""Authentication routes for GitHub OAuth"""

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_current_user_optional, get_db
from pypsa_app.backend.auth.session import get_session_store
from pypsa_app.backend.models import User, UserOAuthProvider, UserRole
from pypsa_app.backend.schemas.auth import UserResponse
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


def _create_session_response(user_id: int, redirect_url: str) -> RedirectResponse:
    """Create a redirect response with a session cookie."""
    session_store = get_session_store()
    session_id = session_store.create_session(user_id)
    response = RedirectResponse(url=redirect_url)
    is_localhost = urlparse(settings.base_url).hostname in (
        "localhost",
        "127.0.0.1",
        "::1",
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=not is_localhost,
        samesite="lax",
        max_age=settings.session_ttl,
    )
    return response


oauth = OAuth()
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",  # noqa: S106
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Redirect to GitHub OAuth login"""
    if not settings.enable_auth:
        raise HTTPException(status_code=400, detail="Authentication is disabled")

    callback_url = f"{settings.base_url}/api/v1/auth/callback"
    # Use authlib to auto-generates state and stores in session
    return await oauth.github.authorize_redirect(request, callback_url)


@router.get("/callback")
async def callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle GitHub OAuth callback"""
    if not settings.enable_auth:
        raise HTTPException(status_code=400, detail="Authentication is disabled")

    try:
        # Use authlib to auto-validates state and raises OAuthError if invalid
        token = await oauth.github.authorize_access_token(request)
    except OAuthError as e:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning("OAuth error (possible CSRF): %s, client_ip=%s", e, client_ip)
        raise HTTPException(status_code=400, detail="Authentication failed") from e

    try:
        # Get user info from GitHub
        resp = await oauth.github.get("user", token=token)
        github_user = resp.json()

        # Get user email (if available)
        email_resp = await oauth.github.get("user/emails", token=token)
        emails = email_resp.json()
        primary_email = next((e["email"] for e in emails if e["primary"]), None)

        # Get Oauth link
        provider_id = str(github_user["id"])
        oauth_link = db.scalars(
            select(UserOAuthProvider).where(
                UserOAuthProvider.provider == "github",
                UserOAuthProvider.provider_id == provider_id,
            )
        ).first()

        if oauth_link:
            # Existing user - just update last_login (profile stays unchanged)
            user = db.get(User, oauth_link.user_id)
            user.update_last_login()
            logger.info("User logged in: %s (role: %s)", user.username, user.role)
        else:
            # New user - first user becomes admin, others are pending
            existing_user = db.scalars(select(User).limit(1)).first()
            is_first_user = existing_user is None

            if is_first_user:
                role = UserRole.ADMIN
                logger.warning("First user %s promoted to admin.", github_user["login"])
            else:
                role = UserRole.PENDING

            user = User(
                username=github_user["login"],
                email=primary_email,
                avatar_url=github_user.get("avatar_url"),
                last_login=datetime.now(UTC),
                role=role,
            )
            db.add(user)
            db.flush()

            oauth_link = UserOAuthProvider(
                user_id=user.id,
                provider="github",
                provider_id=provider_id,
            )
            db.add(oauth_link)
            logger.info("New user registered: %s (role: %s)", user.username, user.role)

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

        response = _create_session_response(user.id, redirect_url)

    except Exception as e:
        logger.exception("OAuth callback error")
        raise HTTPException(status_code=500, detail="Authentication failed") from e
    else:
        return response


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Logout and delete session"""
    if not settings.enable_auth:
        raise HTTPException(status_code=400, detail="Authentication is disabled")

    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if session_id:
        session_store = get_session_store()
        session_store.delete_session(session_id)

    # Clear session cookie
    response = RedirectResponse(url=f"{settings.base_url}/login", status_code=303)
    response.delete_cookie(key=SESSION_COOKIE_NAME)

    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    """Get current authenticated user information"""
    if not settings.enable_auth:
        raise HTTPException(status_code=400, detail="Authentication is disabled")
    if user is None:
        raise HTTPException(
            status_code=401, detail="Authentication required. Please log in."
        )

    return user
