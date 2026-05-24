"""Command-line interface for PyPSA App."""

import os
import sys
import threading
import webbrowser
from importlib.metadata import version
from pathlib import Path

import click
import uvicorn

VERSION = version("pypsa-app")


def _require_frontend_built() -> None:
    """Bail out with a helpful message if the bundled SvelteKit build is missing."""
    static_dir = Path(__file__).parent / "backend" / "static" / "app"
    if not static_dir.exists() or not (static_dir / "index.html").exists():
        click.echo("Error: App frontend not built!", err=True)
        click.echo("   Build with:", err=True)
        click.echo("     cd frontend/app && npm ci && npm run build", err=True)
        click.echo("   Or use --dev flag for API-only mode", err=True)
        sys.exit(1)


class _MainGroup(click.Group):
    """Route bare invocation and leading file path to `open`.

    Registered subcommands resolve normally.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args:
            args = ["open"]
        elif not args[0].startswith("-") and args[0] not in self.commands:
            args = ["open", *args]
        return super().parse_args(ctx, args)


@click.group(cls=_MainGroup, invoke_without_command=True)
@click.version_option(version=VERSION, prog_name="pypsa-app")
def main() -> None:
    """PyPSA Web Application - Visualize and analyze PyPSA network files.

    Run `pypsa-app` for the local dashboard, or `pypsa-app path/to/network.nc`
    to register and open a network in one step.
    """


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to", show_default=True)  # noqa: S104
@click.option(
    "--port", default=8000, type=int, help="Port to bind to", show_default=True
)
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    help="Directory for networks and database (default: ./data)",
)
@click.option(
    "--dev", is_flag=True, help="Development mode (API only, no frontend serving)"
)
@click.option("--reload", is_flag=True, help="Enable auto-reload on code changes")
@click.option(
    "--database-url", help="Database URL (default: sqlite:///./data/pypsa-app.db)"
)
def serve(
    host: str,
    port: int,
    data_dir: Path | None,
    dev: bool,
    reload: bool,
    database_url: str | None,
) -> None:
    """Start the PyPSA web server."""
    # Set up environment
    if data_dir:
        os.environ["DATA_DIR"] = str(data_dir)

    if database_url:
        os.environ["DATABASE_URL"] = database_url

    # Set mode
    if dev:
        os.environ["BACKEND_ONLY"] = "true"
        click.echo(f"   API docs: http://{host}:{port}/docs")
        click.echo("   Start Vite dev server separately: cd frontend && npm run dev")
    else:
        os.environ["BACKEND_ONLY"] = "false"
        click.echo(f"   Application: http://{host}:{port}")
        click.echo(f"   API docs: http://{host}:{port}/api/docs")

    # Check if frontend is built (prod mode)
    if not dev:
        _require_frontend_built()

    # Start server
    click.echo(f"\n   Database: {os.getenv('DATABASE_URL', 'Not configured')}")

    uvicorn.run(
        "pypsa_app.backend.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@main.command(
    name="open",
    short_help="Same as bare `pypsa-app`. Open local single-user dashboard.",
)
@click.argument(
    "file",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--port", default=4743, type=int, help="Port to bind to", show_default=True
)
@click.option("--no-open", is_flag=True, help="Do not open the dashboard in a browser")
def open_cmd(file: Path | None, port: int, no_open: bool) -> None:
    """Open the local single-user dashboard, optionally registering a `.nc` file.

    Equivalent to running `pypsa-app` (no args) or `pypsa-app path/to/network.nc`,
    which are the recommended shortcuts. The file, if given, is registered in
    place (no copy) and opened directly in the browser.
    """
    if file is not None:
        file = file.resolve(strict=True)
        if file.suffix != ".nc":
            click.echo(f"Error: expected a .nc file, got {file.name}", err=True)
            sys.exit(1)

    # Settings read the environment at first instantiation, so these have to
    # be set before any pypsa_app.backend import that touches settings.
    os.environ["LOCAL_MODE"] = "true"
    os.environ["ENABLE_AUTH"] = "false"
    os.environ["BASE_URL"] = f"http://127.0.0.1:{port}"

    _require_frontend_built()

    from pypsa_app.backend.alembic import run_migrations  # noqa: PLC0415
    from pypsa_app.backend.auth.authenticate import ensure_system_user  # noqa: PLC0415
    from pypsa_app.backend.database import SessionLocal  # noqa: PLC0415
    from pypsa_app.backend.services.network import (  # noqa: PLC0415
        register_network_in_place,
    )
    from pypsa_app.backend.settings import settings  # noqa: PLC0415

    settings.networks_path.mkdir(parents=True, exist_ok=True)
    run_migrations()

    network_path = "/networks"
    if file is not None:
        with SessionLocal() as db:
            user = ensure_system_user(db)
            network = register_network_in_place(file, user.id, db)
            db.commit()
            network_path = f"/networks/{network.id}"

    url = f"http://127.0.0.1:{port}{network_path}"
    click.echo(f"\n   Dashboard: {url}")
    click.echo(f"   Database:  {settings.database_url}")
    click.echo(f"   Data dir:  {settings.data_dir_path}\n")

    if not no_open:
        # Delay so uvicorn has time to bind the port and finish startup
        # before the browser races for it.
        threading.Timer(2.5, lambda: webbrowser.open(url)).start()

    uvicorn.run("pypsa_app.backend.main:app", host="127.0.0.1", port=port, reload=False)


@main.command()
def info() -> None:
    """Show information about the installation."""
    click.echo("PyPSA Web App - Installation Info")
    click.echo("=" * 60)
    click.echo(f"Version: {VERSION}")
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo(f"Python executable: {sys.executable}")

    # Check frontend
    static_dir = Path(__file__).parent / "backend" / "static"
    app_dir = static_dir / "app"
    app_built = app_dir.exists() and (app_dir / "index.html").exists()

    if app_built:
        click.echo("\nFrontend: Built and ready")
    else:
        click.echo("\nFrontend: Not built")
        click.echo("   Run: cd frontend/app && npm ci && npm run build")

    click.echo("\nEnvironment variables:")
    for key in [
        "DATA_DIR",
        "DATABASE_URL",
        "BACKEND_ONLY",
        "USE_REDIS",
    ]:
        value = os.getenv(key, "(not set)")
        click.echo(f"  {key}: {value}")

    click.echo("=" * 60)


if __name__ == "__main__":
    main()
