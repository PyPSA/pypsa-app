"""Command-line interface for PyPSA App."""

import os
import sys
from importlib.metadata import version
from pathlib import Path

import click
import uvicorn

VERSION = version("pypsa-app")


@click.group()
@click.version_option(version=VERSION, prog_name="pypsa-app")
def main() -> None:
    """PyPSA Web Application - Visualize and analyze PyPSA network files."""


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
        os.environ["SERVE_FRONTEND"] = "false"
        click.echo(f"   API docs: http://{host}:{port}/docs")
        click.echo("   Start Vite dev server separately: cd frontend && npm run dev")
    else:
        os.environ["SERVE_FRONTEND"] = "true"
        click.echo(f"   Application: http://{host}:{port}")
        click.echo(f"   API docs: http://{host}:{port}/api/docs")

    # Check if frontend is built (prod mode)
    if not dev:
        static_dir = Path(__file__).parent / "backend" / "static"
        app_dir = static_dir / "app"

        if not app_dir.exists() or not (app_dir / "index.html").exists():
            click.echo("Error: App frontend not built!", err=True)
            click.echo("   Build with:", err=True)
            click.echo("     cd frontend/app && npm ci && npm run build", err=True)
            click.echo("   Or use --dev flag for API-only mode", err=True)
            sys.exit(1)

    # Start server
    click.echo(f"\n   Database: {os.getenv('DATABASE_URL', 'Not configured')}")

    uvicorn.run(
        "pypsa_app.backend.main:app",
        host=host,
        port=port,
        reload=reload,
    )


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
        "SERVE_FRONTEND",
        "USE_REDIS",
    ]:
        value = os.getenv(key, "(not set)")
        click.echo(f"  {key}: {value}")

    click.echo("=" * 60)


if __name__ == "__main__":
    main()
