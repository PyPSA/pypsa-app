"""Rename networks.dimensions_count to dimensions, expand payload, add reports, normalize update_history.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


def _decode(value: object) -> object:
    # SQLite stores JSON as TEXT, so raw sa.text() selects return str.
    # Postgres' json/jsonb adapters return parsed objects directly.
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("networks", "dimensions_count", new_column_name="dimensions")
    op.add_column("networks", sa.Column("reports", sa.JSON(), nullable=True))

    bind = op.get_bind()

    # Expand flat counts into structured DimensionsInfo payload.
    dim_keys = ("timesteps", "periods", "scenarios")
    rows = bind.execute(sa.text("SELECT id, dimensions FROM networks")).fetchall()
    for row_id, raw in rows:
        dims = _decode(raw)
        if not isinstance(dims, dict):
            continue
        if all(k in dims and isinstance(dims[k], dict) for k in dim_keys):
            continue
        expanded = {
            "timesteps": {
                "count": int(dims.get("timesteps", 0) or 0),
                "start": None,
                "end": None,
                "freq": None,
            },
            "periods": {
                "count": int(dims.get("periods", 0) or 0),
                "values": [],
                "truncated": False,
            },
            "scenarios": {
                "count": int(dims.get("scenarios", 0) or 0),
                "names": [],
                "truncated": False,
            },
        }
        bind.execute(
            sa.text("UPDATE networks SET dimensions = :d WHERE id = :id").bindparams(
                sa.bindparam("d", value=expanded, type_=sa.JSON()),
                sa.bindparam("id", value=row_id),
            )
        )

    # Normalize update_history timestamps to naive-UTC (strip "+00:00" suffix).
    rows = bind.execute(sa.text("SELECT id, update_history FROM networks")).fetchall()
    for row_id, raw in rows:
        history = _decode(raw)
        if not isinstance(history, list):
            continue
        cleaned = [
            v.removesuffix("+00:00") if isinstance(v, str) else v for v in history
        ]
        if cleaned != history:
            bind.execute(
                sa.text(
                    "UPDATE networks SET update_history = :h WHERE id = :id"
                ).bindparams(
                    sa.bindparam("h", value=cleaned, type_=sa.JSON()),
                    sa.bindparam("id", value=row_id),
                )
            )


def downgrade() -> None:
    bind = op.get_bind()

    # Collapse dimensions back to flat int counts.
    rows = bind.execute(sa.text("SELECT id, dimensions FROM networks")).fetchall()
    for row_id, raw in rows:
        dims = _decode(raw)
        if not isinstance(dims, dict):
            continue
        flat = {}
        for k in ("timesteps", "periods", "scenarios"):
            v = dims.get(k)
            if isinstance(v, dict):
                flat[k] = int(v.get("count", 0) or 0)
            elif isinstance(v, int):
                flat[k] = v
        bind.execute(
            sa.text("UPDATE networks SET dimensions = :d WHERE id = :id").bindparams(
                sa.bindparam("d", value=flat, type_=sa.JSON()),
                sa.bindparam("id", value=row_id),
            )
        )

    op.drop_column("networks", "reports")
    op.alter_column("networks", "dimensions", new_column_name="dimensions_count")
