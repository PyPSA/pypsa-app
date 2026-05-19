"""Add source_path column to networks table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "networks",
        sa.Column("source_path", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("networks", "source_path")
