"""Tests for demo-mode password authentication."""

import secrets
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pypsa_app.backend.auth.session as session_module
import pypsa_app.backend.settings as settings_module
from pypsa_app.backend.alembic import run_migrations
from pypsa_app.backend.api.deps import get_db
from pypsa_app.backend.api.routes.auth import router as auth_router
from pypsa_app.backend.auth.password import DEMO_EMAIL, DEMO_PASSWORD
from pypsa_app.backend.models import User, UserRole


class _FakeSessionStore:
    """In-memory stand-in for the Redis-backed SessionStore."""

    def __init__(self) -> None:
        self._sessions: dict[str, UUID] = {}

    def create_session(self, user_id: UUID) -> str:
        sid = secrets.token_urlsafe(16)
        self._sessions[sid] = user_id
        return sid

    def get_session(self, sid: str) -> UUID | None:
        return self._sessions.get(sid)

    def delete_session(self, sid: str) -> bool:
        return self._sessions.pop(sid, None) is not None


@pytest.fixture
def demo_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """FastAPI app with demo-mode password auth, isolated sqlite DB, and a
    fake session store. Yields (app, SessionFactory) so tests can seed the
    demo user."""
    url = f"sqlite:///{tmp_path}/auth.db"
    monkeypatch.setattr(settings_module.settings, "database_url", url)
    monkeypatch.setattr(settings_module.settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings_module.settings, "auth_github_client_id", None)
    monkeypatch.setattr(settings_module.settings, "auth_github_client_secret", None)
    monkeypatch.setattr(settings_module.settings, "auth_password_enabled", True)
    monkeypatch.setattr(settings_module.settings, "demo_mode", True)
    monkeypatch.setattr(session_module, "session_store", _FakeSessionStore())

    run_migrations()

    engine = create_engine(url)
    Session = sessionmaker(bind=engine, autoflush=False)

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    def _override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db

    try:
        yield app, Session
    finally:
        engine.dispose()


def _seed_demo_user(Session) -> None:
    with Session() as db:
        db.add(User(username="demo", role=UserRole.ADMIN))
        db.commit()


def test_demo_login_success(demo_app) -> None:
    app, Session = demo_app
    _seed_demo_user(Session)

    with TestClient(app) as client:
        r = client.post(
            "/auth/login/password",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        assert r.status_code == 200, r.text
        assert "pypsa_session" in r.cookies


def test_demo_login_wrong_password(demo_app) -> None:
    app, Session = demo_app
    _seed_demo_user(Session)

    with TestClient(app) as client:
        r = client.post(
            "/auth/login/password",
            json={"email": DEMO_EMAIL, "password": "WRONG-pw"},
        )
        assert r.status_code == 401
        assert "pypsa_session" not in r.cookies


def test_demo_login_wrong_email(demo_app) -> None:
    app, Session = demo_app
    _seed_demo_user(Session)

    with TestClient(app) as client:
        r = client.post(
            "/auth/login/password",
            json={"email": "nobody@example.com", "password": DEMO_PASSWORD},
        )
        assert r.status_code == 401


def test_demo_login_disabled_returns_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path}/auth_off.db"
    monkeypatch.setattr(settings_module.settings, "database_url", url)
    monkeypatch.setattr(settings_module.settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings_module.settings, "auth_github_client_id", None)
    monkeypatch.setattr(settings_module.settings, "auth_github_client_secret", None)
    monkeypatch.setattr(settings_module.settings, "auth_password_enabled", False)
    monkeypatch.setattr(settings_module.settings, "demo_mode", False)
    run_migrations()

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    with TestClient(app) as client:
        r = client.post(
            "/auth/login/password",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        assert r.status_code == 400
