"""
Runtime settings store for Mumtaz.

Stores key/value config in the `settings` table so admins can change
SMTP / Stripe / ZATCA / admin-list values from the UI without SSH-editing
.env and restarting uvicorn.

Lookup precedence per key:
    1. settings table (most recent value)
    2. os.environ
    3. default (or None)

Sensitive keys are written as-is but masked when read by `list_all(masked=True)`.
"""

from __future__ import annotations

import os
from typing import Iterable

from db import get_db

DDL_SQLITE = """
    CREATE TABLE IF NOT EXISTS settings (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at INTEGER DEFAULT (strftime('%s','now')),
        updated_by TEXT
    )
"""

DDL_POSTGRES = """
    CREATE TABLE IF NOT EXISTS settings (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at BIGINT DEFAULT extract(epoch from now())::bigint,
        updated_by TEXT
    )
"""

# Settings the admin UI is allowed to read/write.
ALLOWED_KEYS: tuple[str, ...] = (
    # General
    "PORTAL_BASE_URL",
    "MUMTAZ_ADMINS",
    "ERP_API_URL",
    "PORTAL_API_KEY",

    # SMTP
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM", "SMTP_USE_TLS",

    # Stripe
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_STARTER", "STRIPE_PRICE_GROWTH", "STRIPE_PRICE_SCALE",

    # ZATCA
    "ZATCA_ENV", "ZATCA_VAT_NUMBER", "ZATCA_SELLER_NAME",
    "ZATCA_CSID", "ZATCA_PRIVATE_KEY",
)

SENSITIVE_KEYS: tuple[str, ...] = (
    "SMTP_PASS",
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "ZATCA_CSID", "ZATCA_PRIVATE_KEY",
)


def init_db() -> None:
    from db import USE_POSTGRES
    db = get_db()
    ddl = DDL_POSTGRES if USE_POSTGRES else DDL_SQLITE
    db.execute(ddl)
    db.commit()
    db.close()


def get(key: str, default: str | None = None) -> str | None:
    """Get a setting. DB > env > default."""
    if key not in ALLOWED_KEYS:
        return os.environ.get(key, default)
    try:
        db  = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        db.close()
    except Exception:
        row = None
    if row and row.get("value") is not None and row["value"] != "":
        return row["value"]
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
    """Upsert a setting. None or empty string clears it (falls back to env)."""
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Setting '{key}' is not in the allowed list.")
    db = get_db()
    if value is None or value == "":
        db.execute("DELETE FROM settings WHERE key = ?", (key,))
    else:
        db.execute(
            "INSERT INTO settings (key, value, updated_by) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = EXCLUDED.value, updated_by = EXCLUDED.updated_by",
            (key, str(value), updated_by),
        )
    db.commit()
    db.close()


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
    return value[:4] + "…" + value[-4:]


def list_all(masked: bool = True) -> dict:
    """Return all known settings with current value + source."""
    out: dict[str, dict] = {}
    try:
        db   = get_db()
        rows = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings").fetchall()}
        db.close()
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
