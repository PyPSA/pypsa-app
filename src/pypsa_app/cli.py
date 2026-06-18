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
@click.option("--reload", is_flag=True, help="Enable auto-reload on code changes")
@click.option(
    "--database-url", help="Database URL (default: sqlite:///./data/pypsa-app.db)"
)
def serve(
    host: str,
    port: int,
    data_dir: Path | None,
    reload: bool,
    database_url: str | None,
) -> None:
    """Start the PyPSA web server."""
    if data_dir:
        os.environ["DATA_DIR"] = str(data_dir)

    if database_url:
        os.environ["DATABASE_URL"] = database_url

    click.echo(f"   API docs: http://{host}:{port}/docs")
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

    click.echo("\nEnvironment variables:")
    for key in [
        "DATA_DIR",
        "DATABASE_URL",
        "REDIS_URL",
    ]:
        value = os.getenv(key, "(not set)")
        click.echo(f"  {key}: {value}")

    click.echo("=" * 60)


if __name__ == "__main__":
    main()
