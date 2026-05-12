import os

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

import pypsa_app.backend.settings as settings_module


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
    return {"file": "alembic.ini"}


@pytest.fixture
def alembic_engine(db_engine: Engine) -> Engine:
    """Engine alias pytest-alembic looks up by name."""
    return db_engine
