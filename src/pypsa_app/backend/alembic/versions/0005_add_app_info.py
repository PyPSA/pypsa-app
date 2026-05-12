"""Add app_info table for tracking the last pypsa-app version that touched the DB.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Single-row table (enforced by CHECK id=1) holding the last pypsa-app
    # version that ran migrations. Lets newer installs warn when they're about
    # to open a DB written by a newer (incompatible) future version.
    op.create_table(
        "app_info",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_app_version", sa.String(length=64), nullable=False),
        sa.Column("last_migrated_at", sa.TIMESTAMP(), nullable=False),
        sa.CheckConstraint("id = 1", name="app_info_single_row"),
    )


def downgrade() -> None:
    op.drop_table("app_info")
