"""Alembic migration tests.

Built-in pytest-alembic schema checks are re-exported below.
See https://pytest-alembic.readthedocs.io/en/latest/running.html

Data tests follow, one per revision.
"""

import json
import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from pytest_alembic.tests import (  # noqa: F401
    test_model_definitions_match_ddl,
    test_single_head_revision,
    test_up_down_consistency,
    test_upgrade,
)


def _decode_json(value: Any) -> Any:
    # SQLite returns JSON columns as TEXT; postgres returns parsed objects.
    return json.loads(value) if isinstance(value, str) else value


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def network_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def run_id() -> uuid.UUID:
    return uuid.uuid4()


def _insert_user(conn: sa.Connection, uid: uuid.UUID, username: str) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO users (id, username, role) VALUES (:id, :u, 'user')"
        ).bindparams(sa.bindparam("id", type_=sa.Uuid())),
        {"id": uid, "u": username},
    )


# ---------------------------------------------------------------------------
# 0001 — initial schema
# ---------------------------------------------------------------------------


def test_0001_creates_expected_tables(alembic_runner, alembic_engine) -> None:
    alembic_runner.migrate_up_to("0001")

    inspector = sa.inspect(alembic_engine)
    expected = {
        "snakedispatch_backends",
        "users",
        "user_oauth_providers",
        "api_keys",
        "user_backends",
        "runs",
        "networks",
    }
    assert expected.issubset(set(inspector.get_table_names()))


# ---------------------------------------------------------------------------
# 0002 — runs.visibility column with server_default
# ---------------------------------------------------------------------------


def test_0002_backfills_visibility_on_existing_runs(
    alembic_runner,
    alembic_engine,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    alembic_runner.migrate_up_to("0001")

    with alembic_engine.begin() as conn:
        _insert_user(conn, user_id, "carol")
        conn.execute(
            sa.text(
                "INSERT INTO runs (job_id, user_id, workflow, status) "
                "VALUES (:jid, :uid, 'wf', 'PENDING')"
            ).bindparams(
                sa.bindparam("jid", type_=sa.Uuid()),
                sa.bindparam("uid", type_=sa.Uuid()),
            ),
            {"jid": run_id, "uid": user_id},
        )

    alembic_runner.migrate_up_one()  # 0001 -> 0002

    with alembic_engine.connect() as conn:
        visibility = conn.execute(
            sa.text(
                "SELECT visibility FROM runs WHERE job_id = :id"
            ).bindparams(sa.bindparam("id", type_=sa.Uuid())),
            {"id": run_id},
        ).scalar_one()

    assert visibility == "private"


def test_0002_downgrade_drops_visibility_column(
    alembic_runner, alembic_engine
) -> None:
    alembic_runner.migrate_up_to("0002")
    alembic_runner.migrate_down_one()

    inspector = sa.inspect(alembic_engine)
    columns = {c["name"] for c in inspector.get_columns("runs")}
    assert "visibility" not in columns


# ---------------------------------------------------------------------------
# 0003 — dimensions expansion, history normalization, reports column
# ---------------------------------------------------------------------------


def test_0003_upgrade_backfills_dimensions_and_history(
    alembic_runner,
    alembic_engine,
    user_id: uuid.UUID,
    network_id: uuid.UUID,
) -> None:
    alembic_runner.migrate_up_to("0002")

    with alembic_engine.begin() as conn:
        _insert_user(conn, user_id, "alice")
        conn.execute(
            sa.text(
                "INSERT INTO networks "
                "(id, user_id, visibility, filename, file_path, "
                " dimensions_count, update_history) "
                "VALUES (:id, :uid, 'private', 'foo.nc', '/p/foo.nc', "
                ":dims, :hist)"
            ).bindparams(
                sa.bindparam("id", type_=sa.Uuid()),
                sa.bindparam("uid", type_=sa.Uuid()),
                sa.bindparam("dims", type_=sa.JSON()),
                sa.bindparam("hist", type_=sa.JSON()),
            ),
            {
                "id": network_id,
                "uid": user_id,
                "dims": {"timesteps": 8760, "periods": 1, "scenarios": 3},
                "hist": [
                    "2026-01-01T00:00:00+00:00",
                    "2026-02-01T00:00:00+00:00",
                ],
            },
        )

    alembic_runner.migrate_up_one()

    with alembic_engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT dimensions, update_history, reports "
                "FROM networks WHERE id = :id"
            ).bindparams(sa.bindparam("id", type_=sa.Uuid())),
            {"id": network_id},
        ).one()

    dims = _decode_json(row[0])
    hist = _decode_json(row[1])
    reports = _decode_json(row[2])

    assert dims["timesteps"]["count"] == 8760
    assert dims["periods"]["count"] == 1
    assert dims["scenarios"]["count"] == 3
    # Structured payload shape — keys present even when empty.
    assert dims["timesteps"]["start"] is None
    assert dims["periods"]["values"] == []
    assert dims["scenarios"]["truncated"] is False

    assert hist == ["2026-01-01T00:00:00", "2026-02-01T00:00:00"]
    assert reports is None


def test_0003_downgrade_collapses_dimensions(
    alembic_runner,
    alembic_engine,
    user_id: uuid.UUID,
    network_id: uuid.UUID,
) -> None:
    alembic_runner.migrate_up_to("0003")

    expanded = {
        "timesteps": {"count": 100, "start": None, "end": None, "freq": None},
        "periods": {"count": 2, "values": [], "truncated": False},
        "scenarios": {"count": 5, "names": [], "truncated": False},
    }
    with alembic_engine.begin() as conn:
        _insert_user(conn, user_id, "bob")
        conn.execute(
            sa.text(
                "INSERT INTO networks "
                "(id, user_id, visibility, filename, file_path, dimensions) "
                "VALUES (:id, :uid, 'private', 'foo.nc', '/p/foo.nc', :dims)"
            ).bindparams(
                sa.bindparam("id", type_=sa.Uuid()),
                sa.bindparam("uid", type_=sa.Uuid()),
                sa.bindparam("dims", type_=sa.JSON()),
            ),
            {"id": network_id, "uid": user_id, "dims": expanded},
        )

    alembic_runner.migrate_down_one()

    with alembic_engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT dimensions_count FROM networks WHERE id = :id"
            ).bindparams(sa.bindparam("id", type_=sa.Uuid())),
            {"id": network_id},
        ).one()

    assert _decode_json(row[0]) == {"timesteps": 100, "periods": 2, "scenarios": 5}


# ---------------------------------------------------------------------------
# 0004 — is_external column on networks
# ---------------------------------------------------------------------------


def test_0004_backfills_is_external_on_existing_networks(
    alembic_runner,
    alembic_engine,
    user_id: uuid.UUID,
    network_id: uuid.UUID,
) -> None:
    alembic_runner.migrate_up_to("0003")

    with alembic_engine.begin() as conn:
        _insert_user(conn, user_id, "dave")
        conn.execute(
            sa.text(
                "INSERT INTO networks "
                "(id, user_id, visibility, filename, file_path) "
                "VALUES (:id, :uid, 'private', 'foo.nc', '/p/foo.nc')"
            ).bindparams(
                sa.bindparam("id", type_=sa.Uuid()),
                sa.bindparam("uid", type_=sa.Uuid()),
            ),
            {"id": network_id, "uid": user_id},
        )

    alembic_runner.migrate_up_one()  # 0003 -> 0004

    with alembic_engine.connect() as conn:
        is_external = conn.execute(
            sa.text(
                "SELECT is_external FROM networks WHERE id = :id"
            ).bindparams(sa.bindparam("id", type_=sa.Uuid())),
            {"id": network_id},
        ).scalar_one()

    assert bool(is_external) is False


def test_0004_downgrade_drops_is_external_column(
    alembic_runner, alembic_engine
) -> None:
    alembic_runner.migrate_up_to("0004")
    alembic_runner.migrate_down_one()

    inspector = sa.inspect(alembic_engine)
    columns = {c["name"] for c in inspector.get_columns("networks")}
    assert "is_external" not in columns


# ---------------------------------------------------------------------------
# 0005 — app_info single-row table
# ---------------------------------------------------------------------------


def test_0005_creates_app_info_table(alembic_runner, alembic_engine) -> None:
    alembic_runner.migrate_up_to("0005")

    inspector = sa.inspect(alembic_engine)
    assert "app_info" in inspector.get_table_names()
    columns = {c["name"] for c in inspector.get_columns("app_info")}
    assert {"id", "last_app_version", "last_migrated_at"}.issubset(columns)


def test_0005_downgrade_drops_app_info_table(
    alembic_runner, alembic_engine
) -> None:
    alembic_runner.migrate_up_to("0005")
    alembic_runner.migrate_down_one()

    inspector = sa.inspect(alembic_engine)
    assert "app_info" not in inspector.get_table_names()
