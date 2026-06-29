"""Multi-tenant control plane — tenants, users, auth, per-tenant isolation.

ADDITIVE and OFF by default. Set MULTITENANT=1 to enable. When OFF the app runs
exactly as before (one store, nginx basic-auth). When ON:
  * each tenant's client data lives in its OWN SQLite file (strong isolation);
  * a shared control DB holds tenants + users + billing;
  * requests carry a JWT; middleware routes each to its tenant store.

No third-party deps: password hashing is stdlib pbkdf2; JWT is stdlib HMAC.
Secret-at-rest encryption uses Fernet if `cryptography` + C2P_SECRET_KEY are
present, else base64 (set both for real encryption in production).
"""
from __future__ import annotations

import base64
import contextvars
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

from models import Tenant, User

MULTITENANT = os.getenv("MULTITENANT") == "1"
CONTROL_DB = os.getenv("C2P_CONTROL_DB", "control.db")
TENANT_DIR = os.getenv("C2P_TENANT_DIR", "tenants")
JWT_SECRET = os.getenv("C2P_JWT_SECRET", "")
JWT_TTL = int(os.getenv("C2P_JWT_TTL", "604800"))   # 7 days

PUBLIC_PATHS = {"/health", "/auth/signup", "/auth/login", "/stripe/webhook",
                "/docs", "/openapi.json", "/redoc"}
EDITION_RANK = {"delivery": 1, "growth": 2, "agency": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str) -> str:
    s = "".join(ch if ch.isalnum() else "-" for ch in (name or "tenant").lower())
    return "-".join(p for p in s.split("-") if p) or "tenant"


# ── password hashing (stdlib pbkdf2) ──────────────────────────────────────
def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt_b, dk_b = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(salt_b), 200_000)
        return hmac.compare_digest(dk, base64.b64decode(dk_b))
    except Exception:
        return False


# ── JWT (HS256, no deps) ──────────────────────────────────────────────────
def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_jwt(claims: dict) -> str:
    if not JWT_SECRET:
        raise RuntimeError("C2P_JWT_SECRET not set (required for MULTITENANT)")
    header = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = dict(claims)
    payload["exp"] = int(time.time()) + JWT_TTL
    body = _b64u(json.dumps(payload).encode())
    sig = _b64u(hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def read_jwt(token: str) -> Optional[dict]:
    if not JWT_SECRET or not token:
        return None
    try:
        header, body, sig = token.split(".")
        exp_sig = _b64u(hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, exp_sig):
            return None
        payload = json.loads(_b64u_dec(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ── secret encryption (optional Fernet) ───────────────────────────────────
def _fernet():
    key = os.getenv("C2P_SECRET_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        fkey = key.encode() if len(key) == 44 else base64.urlsafe_b64encode(
            hashlib.sha256(key.encode()).digest())
        return Fernet(fkey)
    except Exception:
        return None


def encryption_active() -> bool:
    """True when a real Fernet key is configured (C2P_SECRET_KEY + cryptography);
    otherwise secrets are only base64-obfuscated."""
    return _fernet() is not None


def enc_secret(v: str) -> str:
    f = _fernet()
    if f:
        return "fernet$" + f.encrypt(v.encode()).decode()
    return "plain$" + base64.b64encode(v.encode()).decode()


def dec_secret(v: str) -> str:
    try:
        kind, data = v.split("$", 1)
        if kind == "fernet":
            f = _fernet()
            return f.decrypt(data.encode()).decode() if f else ""
        return base64.b64decode(data).decode()
    except Exception:
        return ""


# ── control store (tenants + users) ───────────────────────────────────────
_CTRL_DDL = """
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT, slug TEXT UNIQUE, edition TEXT, status TEXT,
  stripe_customer_id TEXT, stripe_subscription_id TEXT, created_at TEXT,
  config TEXT NOT NULL DEFAULT '{}', secrets TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, tenant_id TEXT, email TEXT UNIQUE, password_hash TEXT,
  role TEXT, created_at TEXT);
"""


class ControlStore:
    def __init__(self, path: str = CONTROL_DB):
        self.path = path
        with self._c() as c:
            c.executescript(_CTRL_DDL)

    def _c(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _to_tenant(self, r) -> Tenant:
        return Tenant(id=r["id"], name=r["name"], slug=r["slug"],
                      edition=r["edition"] or "delivery", status=r["status"] or "active",
                      stripe_customer_id=r["stripe_customer_id"],
                      stripe_subscription_id=r["stripe_subscription_id"],
                      created_at=r["created_at"] or "", config=json.loads(r["config"] or "{}"))

    def create_tenant(self, t: Tenant, secrets: Optional[dict] = None) -> Tenant:
        with self._c() as c:
            c.execute("""INSERT INTO tenants
                (id,name,slug,edition,status,stripe_customer_id,stripe_subscription_id,created_at,config,secrets)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (t.id, t.name, t.slug, t.edition, t.status, t.stripe_customer_id,
                       t.stripe_subscription_id, t.created_at, json.dumps(t.config),
                       json.dumps(secrets or {})))
        return t

    def get_tenant(self, tid: str) -> Optional[Tenant]:
        with self._c() as c:
            r = c.execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()
            return self._to_tenant(r) if r else None

    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        with self._c() as c:
            r = c.execute("SELECT * FROM tenants WHERE slug=?", (slug,)).fetchone()
            return self._to_tenant(r) if r else None

    def get_tenant_by_customer(self, cust: str) -> Optional[Tenant]:
        with self._c() as c:
            r = c.execute("SELECT * FROM tenants WHERE stripe_customer_id=?", (cust,)).fetchone()
            return self._to_tenant(r) if r else None

    def update_tenant(self, t: Tenant, secrets: Optional[dict] = None) -> Tenant:
        with self._c() as c:
            if secrets:
                cur = c.execute("SELECT secrets FROM tenants WHERE id=?", (t.id,)).fetchone()
                base = json.loads(cur["secrets"]) if cur and cur["secrets"] else {}
                base.update({k: enc_secret(v) for k, v in secrets.items()})
                sec_json = json.dumps(base)
            else:
                cur = c.execute("SELECT secrets FROM tenants WHERE id=?", (t.id,)).fetchone()
                sec_json = cur["secrets"] if cur else "{}"
            c.execute("""UPDATE tenants SET name=?,edition=?,status=?,stripe_customer_id=?,
                         stripe_subscription_id=?,config=?,secrets=? WHERE id=?""",
                      (t.name, t.edition, t.status, t.stripe_customer_id,
                       t.stripe_subscription_id, json.dumps(t.config), sec_json, t.id))
        return t

    def get_secrets(self, tid: str) -> dict:
        with self._c() as c:
            r = c.execute("SELECT secrets FROM tenants WHERE id=?", (tid,)).fetchone()
            raw = json.loads(r["secrets"]) if r and r["secrets"] else {}
            return {k: dec_secret(v) for k, v in raw.items()}

    def create_user(self, u: User, password_hash: str) -> User:
        with self._c() as c:
            c.execute("""INSERT INTO users (id,tenant_id,email,password_hash,role,created_at)
                         VALUES (?,?,?,?,?,?)""",
                      (u.id, u.tenant_id, u.email, password_hash, u.role, u.created_at))
        return u

    def get_user_by_email(self, email: str):
        with self._c() as c:
            r = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not r:
                return None
            return (User(id=r["id"], tenant_id=r["tenant_id"], email=r["email"],
                         role=r["role"] or "owner", created_at=r["created_at"] or ""),
                    r["password_hash"])


# ── per-tenant store registry + proxy ─────────────────────────────────────
_tenant_stores: dict[str, object] = {}
_current = contextvars.ContextVar("current_store", default=None)
_current_secrets: contextvars.ContextVar = contextvars.ContextVar("current_secrets", default={})


def set_current_secrets(s: dict) -> None:
    _current_secrets.set(s or {})


def reset_current_secrets() -> None:
    _current_secrets.set({})


def current_secret(name: str) -> Optional[str]:
    """The current tenant's decrypted secret (e.g. 'anthropic_key'), or None."""
    try:
        return (_current_secrets.get() or {}).get(name) or None
    except Exception:
        return None


def tenant_store(tenant_id: str):
    from store import EngagementStore
    if tenant_id not in _tenant_stores:
        os.makedirs(TENANT_DIR, exist_ok=True)
        _tenant_stores[tenant_id] = EngagementStore(
            path=os.path.join(TENANT_DIR, f"{tenant_id}.db"))
    return _tenant_stores[tenant_id]


def set_current_store(s) -> None:
    _current.set(s)


def reset_current_store() -> None:
    _current.set(None)


class StoreProxy:
    """Routes store calls to the current tenant's store (when set by middleware),
    else the default store. Lets every existing `store.xxx()` call become
    tenant-aware with no change at the call sites."""

    def __init__(self, default):
        object.__setattr__(self, "_default", default)

    def __getattr__(self, name):
        cur = _current.get()
        return getattr(cur if cur is not None else object.__getattribute__(self, "_default"), name)
