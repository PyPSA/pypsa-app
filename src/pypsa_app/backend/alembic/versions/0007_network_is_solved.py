"""Add is_solved and objective columns to networks table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "networks",
        sa.Column(
            "is_solved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("networks", sa.Column("objective", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("networks", "objective")
    op.drop_column("networks", "is_solved")
