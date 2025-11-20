"""
Command-line interface for PyPSA App.
"""

import os
import sys
from importlib.metadata import version
from pathlib import Path

import click
import uvicorn

VERSION = version("pypsa-app")


@click.group()
@click.version_option(version=VERSION, prog_name="pypsa-app")
def main():
    """PyPSA Web Application - Visualize and analyze PyPSA network files."""
    pass


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to", show_default=True)
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
def serve(host, port, data_dir, dev, reload, database_url):
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

    # Check if frontends are built (prod mode)
    if not dev:
        static_dir = Path(__file__).parent / "backend" / "static"
        app_dir = static_dir / "app"
        map_dir = static_dir / "map"

        missing = []
        if not app_dir.exists() or not (app_dir / "index.html").exists():
            missing.append(
                ("App frontend", "cd frontend/app && npm ci && npm run build")
            )
        if not map_dir.exists() or not (map_dir / "index.html").exists():
            missing.append(
                ("Map frontend", "cd frontend/map && npm ci && npm run build")
            )

        if missing:
            click.echo(
                f"Warning: {', '.join(m[0] for m in missing)} not built!", err=True
            )
            click.echo("   Build with:", err=True)
            for _, cmd in missing:
                click.echo(f"     {cmd}", err=True)
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
def info():
    """Show information about the installation."""
    click.echo("PyPSA Web App - Installation Info")
    click.echo("=" * 60)
    click.echo(f"Version: {VERSION}")
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo(f"Python executable: {sys.executable}")

    # Check frontends
    static_dir = Path(__file__).parent / "backend" / "static"
    frontends = [
        ("App", static_dir / "app"),
        ("Map", static_dir / "map"),
    ]

    built = [
        (name, d.exists() and (d / "index.html").exists()) for name, d in frontends
    ]

    if all(status for _, status in built):
        click.echo("\nFrontends: Both built and ready")
    else:
        click.echo("\nFrontends:")
        for (name, _), is_built in zip(frontends, built):
            if is_built:
                click.echo(f"   {name}: Built")
            else:
                click.echo(
                    f"   {name}: Not built (run: cd frontend/{name.lower()} && npm ci && npm run build)"
                )

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
