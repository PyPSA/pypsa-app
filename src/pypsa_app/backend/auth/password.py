"""Demo-mode credential verifier.

Password auth is currently only enabled in DEMO_MODE (enforced in settings)."""

from secrets import compare_digest

from sqlalchemy import select
from sqlalchemy.orm import Session

from pypsa_app.backend.models import User

DEMO_EMAIL = "demo@example.org"
DEMO_PASSWORD = "demopypsa"  # noqa: S105


def verify_demo_credentials(email: str, password: str, db: Session) -> User | None:
    """Return the shared demo user if credentials match the seeded values."""
    email_ok = compare_digest(email.encode(), DEMO_EMAIL.encode())
    password_ok = compare_digest(password.encode(), DEMO_PASSWORD.encode())
    if not (email_ok and password_ok):
        return None
    return db.scalars(select(User).where(User.username == "demo")).first()
