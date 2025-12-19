"""Generate .env.example and markdown docs from Pydantic settings."""

from collections import defaultdict
from pathlib import Path

from pypsa_app.backend.settings import Settings

ROOT = Path(__file__).parent.parent

DOCKER_VARS = """
# Docker Compose
# --------------
# These variables are only used by Docker Compose, not by the Python application.

# Application port
APP_PORT=8000

# PostgreSQL settings (used by postgres container and to build DATABASE_URL)
POSTGRES_HOST=postgres
POSTGRES_DB=pypsa_app
POSTGRES_USER=pypsa_app
POSTGRES_PASSWORD=changeme
POSTGRES_PORT=5432
"""


def get_extra(field, key, default=None):
    return (field.json_schema_extra or {}).get(key, default)


def format_val(v):
    return None if v is None else str(v).lower() if isinstance(v, bool) else str(v)


def is_commented(field):
    dep = get_extra(field, "depends_on")
    if not dep:
        return field.default is None
    dep_field = Settings.model_fields.get(dep)
    return dep_field and dep_field.default in (None, False)


def grouped_fields():
    groups = defaultdict(list)
    for name, field in Settings.model_fields.items():
        groups[get_extra(field, "category", "Other")].append((name, field))
    return groups


def generate_env():
    lines = ["# Copy this file to .env and adjust values as needed.", ""]
    for cat, fields in grouped_fields().items():
        lines += [f"# {cat}", "# " + "-" * len(cat), ""]
        for name, field in fields:
            if field.description:
                lines.append(f"# {field.description}")
            val = format_val(field.default)
            prefix = "# " if is_commented(field) else ""
            lines += [f"{prefix}{name.upper()}={val or ''}", ""]
    return "\n".join(lines) + DOCKER_VARS


def generate_docs():
    lines = [
        "# Configuration Reference",
        "",
        "Environment variables for PyPSA App.",
        "",
    ]
    for cat, fields in grouped_fields().items():
        lines += [
            f"## {cat}",
            "",
            "| Variable | Description | Default |",
            "|----------|-------------|---------|",
        ]
        for name, field in fields:
            val = format_val(field.default)
            default_str = "-" if val is None else f"`{val}`"
            lines.append(
                f"| `{name.upper()}` | {field.description or ''} | {default_str} |"
            )
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    (ROOT / "compose/.env.example").write_text(generate_env())
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/configuration.md").write_text(generate_docs())
    print("Generated compose/.env.example and docs/configuration.md")
