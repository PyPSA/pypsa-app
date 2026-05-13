"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-03-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "snakedispatch_backends" not in existing_tables:
        op.create_table(
            "snakedispatch_backends",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("url", sa.String(512), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
            sa.UniqueConstraint("url"),
        )

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("username", sa.String(255), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("avatar_url", sa.String(512), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.Column("last_login", sa.TIMESTAMP(), nullable=True),
            sa.Column(
                "role",
                sa.Enum(
                    "admin",
                    "user",
                    "bot",
                    "pending",
                    name="user_role",
                    native_enum=True,
                ),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )
        op.create_index(op.f("ix_users_role"), "users", ["role"])

    if "user_oauth_providers" not in existing_tables:
        op.create_table(
            "user_oauth_providers",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("provider_id", sa.String(255), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "provider", "provider_id", name="uq_provider_provider_id"
            ),
        )
        op.create_index(
            op.f("ix_user_oauth_providers_user_id"),
            "user_oauth_providers",
            ["user_id"],
        )

    if "api_keys" not in existing_tables:
        op.create_table(
            "api_keys",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("key_hash", sa.String(64), nullable=False),
            sa.Column("key_prefix", sa.String(8), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.Column("last_used_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True
        )
        op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"])

    if "user_backends" not in existing_tables:
        op.create_table(
            "user_backends",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("backend_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["backend_id"],
                ["snakedispatch_backends.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("user_id", "backend_id"),
        )

    if "runs" not in existing_tables:
        op.create_table(
            "runs",
            sa.Column("job_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("backend_id", sa.Uuid(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.Column("workflow", sa.Text(), nullable=False),
            sa.Column("configfile", sa.String(512), nullable=True),
            sa.Column("snakemake_args", sa.JSON(), nullable=True),
            sa.Column("extra_files", sa.JSON(), nullable=True),
            sa.Column("cache", sa.JSON(), nullable=True),
            sa.Column("callback_url", sa.String(512), nullable=True),
            sa.Column("git_ref", sa.String(255), nullable=True),
            sa.Column("git_sha", sa.String(40), nullable=True),
            sa.Column(
                "status",
                sa.Enum(
                    "PENDING",
                    "SETUP",
                    "RUNNING",
                    "UPLOADING",
                    "COMPLETED",
                    "FAILED",
                    "ERROR",
                    "CANCELLED",
                    name="run_status",
                    native_enum=True,
                ),
                nullable=False,
            ),
            sa.Column("exit_code", sa.Integer(), nullable=True),
            sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("import_networks", sa.JSON(), nullable=True),
            sa.Column("total_job_count", sa.Integer(), nullable=True),
            sa.Column("jobs_finished", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["backend_id"],
                ["snakedispatch_backends.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("job_id"),
        )
        op.create_index(op.f("ix_runs_user_id"), "runs", ["user_id"])
        op.create_index(op.f("ix_runs_backend_id"), "runs", ["backend_id"])

    if "networks" not in existing_tables:
        op.create_table(
            "networks",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("source_run_id", sa.Uuid(), nullable=True),
            sa.Column(
                "visibility",
                sa.Enum(
                    "public",
                    "private",
                    name="network_visibility",
                    native_enum=True,
                ),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                index=True,
            ),
            sa.Column("update_history", sa.JSON(), nullable=True),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("file_size", sa.BigInteger(), nullable=True),
            sa.Column("file_hash", sa.String(64), nullable=True),
            sa.Column("name", sa.String(255), nullable=True),
            sa.Column("dimensions_count", sa.JSON(), nullable=True),
            sa.Column("components_count", sa.JSON(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("facets", sa.JSON(), nullable=True),
            sa.Column("topology_svg", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["source_run_id"], ["runs.job_id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_networks_user_id"), "networks", ["user_id"])
        op.create_index(
            op.f("ix_networks_source_run_id"), "networks", ["source_run_id"]
        )
        op.create_index(op.f("ix_networks_visibility"), "networks", ["visibility"])
        op.create_index(
            op.f("ix_networks_file_path"),
            "networks",
            ["file_path"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_table("networks")
    op.drop_table("runs")
    op.drop_table("user_backends")
    op.drop_table("api_keys")
    op.drop_table("user_oauth_providers")
    op.drop_table("users")
    op.drop_table("snakedispatch_backends")

    # Postgres: drop ENUM types so re-upgrade does not hit DuplicateObject
    if op.get_bind().dialect.name == "postgresql":
        for enum_name in ("network_visibility", "run_status", "user_role"):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
