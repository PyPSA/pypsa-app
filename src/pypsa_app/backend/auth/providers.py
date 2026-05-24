"""Declarative OAuth provider registry and helpers.

Adding a new provider takes one entry in OAUTH_PROVIDERS plus two settings
fields (AUTH_<NAME>_CLIENT_ID / AUTH_<NAME>_CLIENT_SECRET).
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from pypsa_app.backend.models import User
    from pypsa_app.backend.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonicalOAuthUser:
    """Provider-agnostic user identity returned by every fetch_user impl."""

    provider_id: str
    username: str
    email: str | None
    avatar_url: str | None


@dataclass(frozen=True)
class OAuthProviderSpec:
    id: str
    display_name: str
    icon: str | None
    authorize_url: str
    access_token_url: str
    api_base_url: str
    scope: str
    fetch_user: Callable[[Any, dict[str, Any]], Awaitable[CanonicalOAuthUser]]


async def _fetch_github_user(client: Any, token: dict[str, Any]) -> CanonicalOAuthUser:
    # Primary email needs a separate /user/emails call.
    user_resp = await client.get("user", token=token)
    info = user_resp.json()
    emails_resp = await client.get("user/emails", token=token)
    primary = next((e["email"] for e in emails_resp.json() if e["primary"]), None)
    return CanonicalOAuthUser(
        provider_id=str(info["id"]),
        username=info["login"],
        email=primary,
        avatar_url=info.get("avatar_url"),
    )


OAUTH_PROVIDERS: dict[str, OAuthProviderSpec] = {
    "github": OAuthProviderSpec(
        id="github",
        display_name="GitHub",
        icon="github",
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",  # noqa: S106
        api_base_url="https://api.github.com/",
        scope="user:email",
        fetch_user=_fetch_github_user,
    ),
}


_oauth = OAuth()
_clients: dict[str, Any] = {}


def _register_client(settings: "Settings", pid: str) -> Any:
    spec = OAUTH_PROVIDERS[pid]
    _oauth.register(
        name=pid,
        client_id=getattr(settings, f"auth_{pid}_client_id"),
        client_secret=getattr(settings, f"auth_{pid}_client_secret"),
        authorize_url=spec.authorize_url,
        access_token_url=spec.access_token_url,
        api_base_url=spec.api_base_url,
        client_kwargs={"scope": spec.scope},
    )
    client = getattr(_oauth, pid)
    _clients[pid] = client
    return client


def build_oauth_clients(settings: "Settings") -> None:
    """Register a client for each enabled provider. Safe to call repeatedly."""
    for pid in settings.enabled_oauth_providers:
        if pid not in _clients:
            _register_client(settings, pid)


def get_oauth_client(settings: "Settings", provider: str) -> Any:
    """Return authlib client, registering it on first access."""
    return _clients.get(provider) or _register_client(settings, provider)


def login_or_register_oauth_user(
    db: "Session", *, provider: str, canonical: CanonicalOAuthUser
) -> "User":
    """Find or create a user linked to the given OAuth identity.

    First user ever to log in is promoted to admin. Later new users land in
    PENDING until an admin approves them.
    """
    from pypsa_app.backend.models import (  # noqa: PLC0415
        User,
        UserOAuthProvider,
        UserRole,
    )

    oauth_link = db.scalars(
        select(UserOAuthProvider).where(
            UserOAuthProvider.provider == provider,
            UserOAuthProvider.provider_id == canonical.provider_id,
        )
    ).first()

    user: User | None = None
    if oauth_link:
        user = db.get(User, oauth_link.user_id)
        if user is None:
            logger.warning(
                "Orphan oauth_link for %s/%s -> user_id=%s;"
                " deleting and re-registering",
                provider,
                canonical.provider_id,
                oauth_link.user_id,
            )
            db.delete(oauth_link)
            db.flush()
            oauth_link = None

    if user is not None:
        user.update_last_login()
        logger.info("User logged in: %s (role: %s)", user.username, user.role)
    else:
        if db.scalars(select(User).limit(1)).first() is None:
            role = UserRole.ADMIN
            logger.warning("First user %s promoted to admin.", canonical.username)
        else:
            role = UserRole.PENDING

        user = User(
            username=canonical.username,
            email=canonical.email,
            avatar_url=canonical.avatar_url,
            role=role,
        )
        user.update_last_login()
        db.add(user)
        db.flush()

        oauth_link = UserOAuthProvider(
            user_id=user.id,
            provider=provider,
            provider_id=canonical.provider_id,
        )
        db.add(oauth_link)
        logger.info("New user registered: %s (role: %s)", user.username, user.role)

    return user
