"""Alembic migration helpers."""

from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from pypsa_app import __version__
from pypsa_app.backend.settings import settings


class DatabaseVersionMismatchError(RuntimeError):
    """Database was previously migrated by a newer pypsa-app version and can no longer be opened with this older one."""


def run_migrations() -> None:
    """Upgrade the DB, refusing if it was already migrated by a newer pypsa-app."""
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent))
    known = {r.revision for r in ScriptDirectory.from_config(cfg).walk_revisions()}

    engine = create_engine(settings.database_url)
    try:
        before: str | None = None
        with engine.connect() as conn:
            insp = inspect(conn)
            if insp.has_table("alembic_version"):
                before = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if before and before not in known:
                    wrote = None
                    if insp.has_table("app_info"):
                        wrote = conn.execute(
                            text("SELECT last_app_version FROM app_info WHERE id = 1")
                        ).scalar()
                    msg = (
                        f"Database is at migration {before!r}, unknown to pypsa-app "
                        f"{__version__}. The database was previously migrated by a newer "
                        f"pypsa-app version and can no longer be opened with this older one. "
                        f"Upgrade pypsa-app to continue."
                    )
                    if wrote:
                        msg += f" Last written by pypsa-app {wrote}."
                    raise DatabaseVersionMismatchError(msg)

        command.upgrade(cfg, "head")

        with engine.begin() as conn:
            after = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if after != before and inspect(conn).has_table("app_info"):
                conn.execute(
                    text(
                        "INSERT INTO app_info (id, last_app_version, last_migrated_at) "
                        "VALUES (1, :v, :t) "
                        "ON CONFLICT (id) DO UPDATE SET "
                        "last_app_version = excluded.last_app_version, "
                        "last_migrated_at = excluded.last_migrated_at"
                    ),
                    {"v": __version__, "t": datetime.now(UTC).replace(tzinfo=None)},
                )
    finally:
        engine.dispose()
