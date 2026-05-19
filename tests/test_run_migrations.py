"""Tests for the run_migrations helper (newer-DB guard, version stamping)."""

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from pypsa_app import __version__
from pypsa_app.backend.alembic import (
    DatabaseVersionMismatchError,
    run_migrations,
)


def test_run_migrations_upgrades_fresh_db_and_stamps_version(
    db_engine: Engine,
) -> None:
    run_migrations()

    with db_engine.connect() as conn:
        version = conn.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()
        app_row = conn.execute(
            sa.text("SELECT id, last_app_version FROM app_info WHERE id = 1")
        ).one()

    assert version == "0006"
    assert app_row.id == 1
    assert app_row.last_app_version == __version__


def test_run_migrations_refuses_when_db_is_at_unknown_revision(
    db_engine: Engine,
) -> None:
    run_migrations()

    with db_engine.begin() as conn:
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '9999'"))

    with pytest.raises(DatabaseVersionMismatchError, match="9999"):
        run_migrations()
