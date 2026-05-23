"""
Pytest fixtures for the Mumtaz platform API.

Uses a shared in-memory SQLite database so tests run without PostgreSQL
or a real Odoo instance. The app is created fresh for each test session.
"""
import os
import pytest
import time

# Force development mode so JWT_SECRET / CORS crash-guards don't fire
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
# Point to in-memory SQLite — never touches PostgreSQL during tests
os.environ.pop("DATABASE_URL", None)

from fastapi.testclient import TestClient
from main import app, make_token, init_db, SECRET, ALGO
from db import get_db


@pytest.fixture(scope="session", autouse=True)
def _init_database():
    """Run DDL once per test session."""
    import settings_store
    init_db()
    settings_store.init_db()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    conn = get_db()
    yield conn
    conn.close()


def _make_user(db, *, email: str, password_hash: str = None, role: str = None,
               plan: str = "trial", active: int = 1) -> int:
    """Insert a user row and return its id."""
    import bcrypt as _bcrypt
    pw = password_hash or _bcrypt.hashpw(b"TestPass123!", _bcrypt.gensalt()).decode()
    name = email.split("@")[0]
    db.execute(
        "INSERT INTO users (email, password_hash, name, plan, active, role) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (email, pw, name, plan, active, role),
    )
    db.commit()
    row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    return row["id"]


@pytest.fixture
def regular_user(db):
    uid = _make_user(db, email="user@test.mumtaz.digital")
    token = make_token(uid, "user@test.mumtaz.digital", {"plan": "trial"})
    yield {"id": uid, "email": "user@test.mumtaz.digital", "token": token}
    db.execute("DELETE FROM users WHERE email=?", ("user@test.mumtaz.digital",))
    db.commit()


@pytest.fixture
def admin_user(db):
    uid = _make_user(db, email="admin@test.mumtaz.digital", role="admin", plan="growth")
    token = make_token(uid, "admin@test.mumtaz.digital", {"plan": "growth", "role": "admin"})
    yield {"id": uid, "email": "admin@test.mumtaz.digital", "token": token}
    db.execute("DELETE FROM users WHERE email=?", ("admin@test.mumtaz.digital",))
    db.commit()
