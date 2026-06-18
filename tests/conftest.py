import os
from pathlib import Path

import pypsa
import pytest
import sqlalchemy as sa
from fastapi import APIRouter, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

import pypsa_app.backend.settings as settings_module
from pypsa_app.backend.alembic import run_migrations
from pypsa_app.backend.api.deps import get_current_user_optional, get_db
from pypsa_app.backend.models import User, UserRole


def _engine_params() -> list:
    params = [pytest.param("sqlite", id="sqlite")]
    if os.environ.get("TEST_POSTGRES_URL"):
        params.append(pytest.param("postgres", id="postgres"))
    else:
        params.append(
            pytest.param(
                "postgres",
                id="postgres",
                marks=pytest.mark.skip(reason="TEST_POSTGRES_URL not set"),
            )
        )
    return params


@pytest.fixture(params=_engine_params())
def db_engine(
    request: pytest.FixtureRequest,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Clean SQLAlchemy engine, parametrized over sqlite + postgres."""
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path}/test.db"
    else:
        url = os.environ["TEST_POSTGRES_URL"]

    monkeypatch.setattr(settings_module.settings, "database_url", url)

    engine: Engine = create_engine(url)

    if request.param == "postgres":
        with engine.begin() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def alembic_config() -> dict[str, str]:
    """Point pytest-alembic at the project alembic.ini."""
    ini = Path(__file__).parent.parent / "alembic.ini"
    return {"file": str(ini)}


@pytest.fixture
def alembic_engine(db_engine: Engine) -> Engine:
    """Engine alias pytest-alembic looks up by name."""
    return db_engine


@pytest.fixture
def nc_file(tmp_path: Path) -> Path:
    """A minimal but valid PyPSA NetCDF file."""
    n = pypsa.Network()
    n.add("Bus", "b0")
    out = tmp_path / "sample.nc"
    n.export_to_netcdf(out)
    return out


@pytest.fixture
def app_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Factory: build a FastAPI test app with isolated sqlite DB and admin user."""
    engines: list[Engine] = []

    def _make(
        *routers: tuple[APIRouter, str],
        **settings_overrides: object,
    ) -> FastAPI:
        url = f"sqlite:///{tmp_path}/test.db"
        monkeypatch.setattr(settings_module.settings, "database_url", url)
        monkeypatch.setattr(settings_module.settings, "data_dir", str(tmp_path))
        monkeypatch.setattr(settings_module.settings, "auth_github_client_id", None)
        monkeypatch.setattr(settings_module.settings, "auth_github_client_secret", None)
        monkeypatch.setattr(settings_module.settings, "auth_password_enabled", False)
        for name, value in settings_overrides.items():
            monkeypatch.setattr(settings_module.settings, name, value)
        run_migrations()

        engine = create_engine(url)
        engines.append(engine)
        Session = sessionmaker(bind=engine, autoflush=False)

        with Session() as db:
            admin = User(username="system", role=UserRole.ADMIN)
            db.add(admin)
            db.commit()
            user_id = admin.id

        app = FastAPI()
        for router, prefix in routers:
            app.include_router(router, prefix=prefix)

        def _override_db():
            s = Session()
            try:
                yield s
            finally:
                s.close()

        async def _override_user():
            s = Session()
            try:
                return s.get(User, user_id)
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user_optional] = _override_user
        return app

    yield _make
    for engine in engines:
        engine.dispose()
