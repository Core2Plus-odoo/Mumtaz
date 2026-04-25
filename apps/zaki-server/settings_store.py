"""
Runtime settings store for Mumtaz.

Stores key/value config in the SQLite `settings` table so admins can change
SMTP / Stripe / ZATCA / admin-list values from the UI without SSH-editing
.env and restarting uvicorn.

Lookup precedence per key:
    1. settings table (most recent value)
    2. os.environ
    3. default (or None)

Sensitive keys (passwords, secret keys, private keys) are written as-is but
masked when read by `list_all(masked=True)`.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable

DB_PATH = os.environ.get("DB_PATH", "/opt/zaki-server/users.db")

DDL = """
    CREATE TABLE IF NOT EXISTS settings (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at INTEGER DEFAULT (strftime('%s','now')),
        updated_by TEXT
    )
"""

# Settings the admin UI is allowed to read/write. Anything not listed here
# is rejected to prevent accidental injection of arbitrary keys.
ALLOWED_KEYS: tuple[str, ...] = (
    # General
    "PORTAL_BASE_URL",
    "MUMTAZ_ADMINS",

    # SMTP
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM", "SMTP_USE_TLS",

    # Stripe
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_STARTER", "STRIPE_PRICE_GROWTH", "STRIPE_PRICE_SCALE",

    # ZATCA
    "ZATCA_ENV", "ZATCA_VAT_NUMBER", "ZATCA_SELLER_NAME",
    "ZATCA_CSID", "ZATCA_PRIVATE_KEY",
)

# Keys that are masked when listed (returned as e.g. "sk_…last4chars" or "set").
SENSITIVE_KEYS: tuple[str, ...] = (
    "SMTP_PASS",
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "ZATCA_CSID", "ZATCA_PRIVATE_KEY",
)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(DDL)
    conn.commit()
    conn.close()


def get(key: str, default: str | None = None) -> str | None:
    """Get a setting. DB > env > default."""
    if key not in ALLOWED_KEYS:
        # Permit reads of any env var even if not in ALLOWED_KEYS (read-only fallback).
        return os.environ.get(key, default)
    try:
        conn = sqlite3.connect(DB_PATH)
        row  = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
    except Exception:
        row = None
    if row and row[0] is not None and row[0] != "":
        return row[0]
    return os.environ.get(key, default)


def get_int(key: str, default: int = 0) -> int:
    v = get(key)
    try:
        return int(v) if v is not None and v != "" else default
    except (ValueError, TypeError):
        return default


def get_bool(key: str, default: bool = False) -> bool:
    v = get(key)
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def set_value(key: str, value: str | None, updated_by: str | None = None) -> None:
    """Upsert a setting. None or empty value clears it (falls back to env)."""
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Setting '{key}' is not in the allowed list.")
    conn = sqlite3.connect(DB_PATH)
    if value is None or value == "":
        conn.execute("DELETE FROM settings WHERE key=?", (key,))
    else:
        conn.execute(
            "INSERT INTO settings (key, value, updated_by) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=strftime('%s','now'), updated_by=excluded.updated_by",
            (key, str(value), updated_by),
        )
    conn.commit()
    conn.close()


def set_many(values: dict, updated_by: str | None = None) -> list[str]:
    """Update multiple keys at once. Returns the list of accepted keys."""
    accepted: list[str] = []
    for k, v in values.items():
        if k not in ALLOWED_KEYS:
            continue
        set_value(k, v, updated_by=updated_by)
        accepted.append(k)
    return accepted


def _mask(value: str | None, key: str) -> str | None:
    if value is None or value == "":
        return None
    if key not in SENSITIVE_KEYS:
        return value
    if len(value) <= 6:
        return "***"
    # Stripe keys & similar — show prefix + last 4
    return value[:4] + "…" + value[-4:]


def list_all(masked: bool = True) -> dict:
    """Return all known settings with current value + source."""
    out: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = {r[0]: r[1] for r in conn.execute("SELECT key, value FROM settings").fetchall()}
        conn.close()
    except Exception:
        rows = {}
    for key in ALLOWED_KEYS:
        db_val = rows.get(key)
        if db_val is not None and db_val != "":
            out[key] = {
                "value":     _mask(db_val, key) if masked else db_val,
                "source":    "db",
                "is_secret": key in SENSITIVE_KEYS,
            }
        else:
            env_val = os.environ.get(key)
            if env_val:
                out[key] = {
                    "value":     _mask(env_val, key) if masked else env_val,
                    "source":    "env",
                    "is_secret": key in SENSITIVE_KEYS,
                }
            else:
                out[key] = {"value": None, "source": "unset", "is_secret": key in SENSITIVE_KEYS}
    return out
