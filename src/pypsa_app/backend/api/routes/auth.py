"""Authentication routes for GitHub OAuth"""

import logging
from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_current_user, get_db
from pypsa_app.backend.auth.session import get_session_store
from pypsa_app.backend.models import User, UserOAuthProvider, UserRole
from pypsa_app.backend.schemas.auth import UserResponse
from pypsa_app.backend.settings import SESSION_COOKIE_NAME, settings

logger = logging.getLogger(__name__)
router = APIRouter()

oauth = OAuth()
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)


@router.get("/login")
async def login(request: Request):
    """Redirect to GitHub OAuth login"""
    if not settings.enable_auth:
        raise HTTPException(status_code=400, detail="Authentication is disabled")

    callback_url = f"{settings.base_url}/api/v1/auth/callback"
    # Use authlib to auto-generates state and stores in session
    return await oauth.github.authorize_redirect(request, callback_url)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    if not settings.enable_auth:
        raise HTTPException(status_code=400, detail="Authentication is disabled")

    try:
        # Use authlib to auto-validates state and raises OAuthError if invalid
        token = await oauth.github.authorize_access_token(request)
    except OAuthError as e:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"OAuth error (possible CSRF): {e}, client_ip={client_ip}")
        raise HTTPException(status_code=400, detail="Authentication failed")

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
        oauth_link = (
            db.query(UserOAuthProvider)
            .filter(
                UserOAuthProvider.provider == "github",
                UserOAuthProvider.provider_id == provider_id,
            )
            .first()
        )

        if oauth_link:
            # Existing user - just update last_login (profile stays unchanged)
            user = db.query(User).filter(User.id == oauth_link.user_id).first()
            user.update_last_login()
            logger.info(f"User logged in: {user.username} (role: {user.role})")
        else:
            # New user - first user becomes admin, others are pending
            existing_user = db.query(User).limit(1).first()
            is_first_user = existing_user is None

            if is_first_user:
                role = UserRole.ADMIN
                logger.warning(f"First user {github_user['login']} promoted to admin.")
            else:
                role = UserRole.PENDING

            user = User(
                username=github_user["login"],
                email=primary_email,
                avatar_url=github_user.get("avatar_url"),
                last_login=datetime.now(timezone.utc),
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
            logger.info(f"New user registered: {user.username} (role: {user.role})")

        db.commit()
        db.refresh(user)

        session_store = get_session_store()
        session_id = session_store.create_session(user.id)

        # Redirect based on role
        redirect_url = settings.base_url
        if user.role == UserRole.PENDING:
            redirect_url = f"{settings.base_url}/pending-approval"

        # Set session cookie
        response = RedirectResponse(url=redirect_url)
        is_localhost = "localhost" in settings.base_url
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            httponly=True,
            secure=not is_localhost,
            samesite="lax",
            max_age=settings.session_ttl,
        )

        return response

    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/logout")
async def logout(request: Request):
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
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    if not settings.enable_auth:
        raise HTTPException(status_code=400, detail="Authentication is disabled")

    return user
