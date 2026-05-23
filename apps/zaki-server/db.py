"""
Database abstraction layer.

Supports SQLite (development) and PostgreSQL (production).

Set DATABASE_URL=postgresql://user:pass@host:5432/dbname for production.
Falls back to SQLite at DB_PATH when DATABASE_URL is unset or begins with 'sqlite'.

Usage (identical to the old sqlite3 pattern):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.commit()
    db.close()

Rows returned by fetchone()/fetchall() are plain dicts.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Sequence

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
DB_PATH: str = os.environ.get("DB_PATH", "/opt/zaki-server/users.db")

USE_POSTGRES: bool = bool(DATABASE_URL) and (
    DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")
)

# ── PostgreSQL connection pool (lazy init) ────────────────────────────
_pg_pool: Any = None  # psycopg2.pool.ThreadedConnectionPool

if USE_POSTGRES:
    try:
        import psycopg2                           # type: ignore
        import psycopg2.extras                    # type: ignore
        import psycopg2.pool as _psycopg2_pool    # type: ignore
    except ImportError as _exc:
        raise ImportError(
            "psycopg2-binary is required when DATABASE_URL is a PostgreSQL URL. "
            "Install it: pip install psycopg2-binary"
        ) from _exc


def _init_pool() -> None:
    global _pg_pool
    if USE_POSTGRES and _pg_pool is None:
        _pg_pool = _psycopg2_pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=int(os.environ.get("DB_POOL_MAX", "20")),
            dsn=DATABASE_URL,
        )


def _q(sql: str) -> str:
    """Translate SQLite ? placeholders to psycopg2 %s."""
    return sql.replace("?", "%s") if USE_POSTGRES else sql


# ── Result wrappers ───────────────────────────────────────────────────

class _PgResult:
    """Wraps a psycopg2 RealDictCursor to match sqlite3 cursor API."""
    def __init__(self, cur: Any) -> None:
        self._cur = cur

    def fetchone(self) -> dict | None:
        row = self._cur.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self) -> list[dict]:
        return [dict(r) for r in (self._cur.fetchall() or [])]

    def __iter__(self):
        for row in self._cur:
            yield dict(row)


class _SqResult:
    """Wraps sqlite3.Cursor and returns dicts from fetchone/fetchall."""
    def __init__(self, cur: sqlite3.Cursor) -> None:
        self._cur = cur

    def fetchone(self) -> dict | None:
        row = self._cur.fetchone()
        if row is None:
            return None
        if isinstance(row, sqlite3.Row):
            return dict(row)
        # raw tuple (row_factory not set)
        if self._cur.description:
            keys = [d[0] for d in self._cur.description]
            return dict(zip(keys, row))
        return None

    def fetchall(self) -> list[dict]:
        rows = self._cur.fetchall()
        if not rows:
            return []
        if rows and isinstance(rows[0], sqlite3.Row):
            return [dict(r) for r in rows]
        if self._cur.description:
            keys = [d[0] for d in self._cur.description]
            return [dict(zip(keys, r)) for r in rows]
        return []

    def __iter__(self):
        for row in self._cur:
            if isinstance(row, sqlite3.Row):
                yield dict(row)
            elif self._cur.description:
                keys = [d[0] for d in self._cur.description]
                yield dict(zip(keys, row))


# ── Unified connection class ──────────────────────────────────────────

class Conn:
    """Thin wrapper providing a unified sqlite3-compatible interface."""

    def __init__(self) -> None:
        if USE_POSTGRES:
            _init_pool()
            self._pg = _pg_pool.getconn()
            self._pg.autocommit = False
            self._sq: sqlite3.Connection | None = None
        else:
            import os as _os
            db_dir = os.path.dirname(DB_PATH)
            if db_dir:
                _os.makedirs(db_dir, exist_ok=True)
            self._sq = sqlite3.connect(DB_PATH, check_same_thread=False)
            self._sq.row_factory = sqlite3.Row
            self._pg = None

    def execute(self, sql: str, params: Sequence = ()) -> _PgResult | _SqResult:
        if self._pg is not None:
            cur = self._pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(_q(sql), params or None)
            return _PgResult(cur)
        else:
            assert self._sq is not None
            cur = self._sq.execute(sql, params)
            return _SqResult(cur)

    def executemany(self, sql: str, params_list: Sequence[Sequence]) -> None:
        if self._pg is not None:
            cur = self._pg.cursor()
            cur.executemany(_q(sql), params_list)
        else:
            assert self._sq is not None
            self._sq.executemany(sql, params_list)

    def commit(self) -> None:
        if self._pg is not None:
            self._pg.commit()
        elif self._sq is not None:
            self._sq.commit()

    def rollback(self) -> None:
        if self._pg is not None:
            self._pg.rollback()
        elif self._sq is not None:
            self._sq.rollback()

    def close(self) -> None:
        if self._pg is not None:
            _pg_pool.putconn(self._pg)
            self._pg = None
        elif self._sq is not None:
            self._sq.close()
            self._sq = None

    def __enter__(self) -> "Conn":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def get_db() -> Conn:
    """Return a database connection. Caller is responsible for calling .close()."""
    return Conn()


def add_column_if_missing(db: Conn, table: str, column: str, definition: str) -> None:
    """Add a column to a table if it doesn't already exist (handles both backends)."""
    if USE_POSTGRES:
        try:
            db.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"
            )
        except Exception:
            db.rollback()
    else:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except Exception:
            pass  # Column already exists


def column_exists(db: Conn, table: str, column: str) -> bool:
    """Check whether a column exists in a table."""
    if USE_POSTGRES:
        row = db.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = ?",
            (table, column),
        ).fetchone()
    else:
        rows = db.execute(f"PRAGMA table_info({table})").fetchall()
        row = next((r for r in rows if r.get("name") == column), None)
    return row is not None
