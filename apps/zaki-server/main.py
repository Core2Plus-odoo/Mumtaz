"""
Mumtaz Auth & AI API
- Single auth backend for all Mumtaz products (portal, ERP, ZAKI CFO, marketplace)
- Validates credentials against Odoo via XML-RPC (single source of truth)
- Creates Odoo users + mumtaz.tenant records on signup
- Issues JWT used by all frontends
"""

import os, json, re, time, sqlite3, logging, secrets as _secrets
import xmlrpc.client
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("mumtaz")

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from jose import jwt, JWTError
import bcrypt as _bcrypt
from anthropic import Anthropic
from dotenv import load_dotenv

import mail as mailer
import billing as billing_svc
import zatca as zatca_svc
import settings_store as settings

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────
_env_mode   = os.environ.get("ENVIRONMENT", "production").lower()

_raw_secret = os.environ.get("JWT_SECRET", "")
if not _raw_secret or _raw_secret in ("change-me-in-production", "dev-only-insecure-secret-not-for-production"):
    if _env_mode != "development":
        raise RuntimeError(
            "[FATAL] JWT_SECRET is not set or uses the insecure default. "
            "Generate a strong secret with: openssl rand -hex 64"
        )
    _raw_secret = "dev-only-insecure-secret-not-for-production"
SECRET      = _raw_secret
ALGO        = "HS256"
TOKEN_HOURS = int(os.environ.get("TOKEN_HOURS", "24"))
ANT_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
ZAKI_MODEL  = os.environ.get("ZAKI_MODEL",         "claude-opus-4-7")
DB_PATH     = os.environ.get("DB_PATH",            "/opt/zaki-server/users.db")

ODOO_URL    = os.environ.get("ODOO_URL",            "http://127.0.0.1:8069")
ODOO_DB     = os.environ.get("ODOO_DB",             "mumtaz")
ODOO_ADMIN  = os.environ.get("ODOO_ADMIN_USER",     "admin")
ODOO_PASS   = os.environ.get("ODOO_ADMIN_PASS",     "admin")
ODOO_TIMEOUT = int(os.environ.get("ODOO_TIMEOUT",   "15"))

if ODOO_PASS in ("admin", "password", "odoo", "") and _env_mode != "development":
    raise RuntimeError(
        "[FATAL] ODOO_ADMIN_PASS is set to a weak default. "
        "Set a strong password in your .env file."
    )

def _hash_pw(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def _verify_pw(password: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

# ── App ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.init_db()
    yield

app = FastAPI(title="Mumtaz Auth & AI API", version="2.0.0", lifespan=lifespan)

_cors_raw    = os.environ.get("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
if not CORS_ORIGINS:
    if _env_mode != "development":
        raise RuntimeError(
            "[FATAL] CORS_ORIGINS is not set. "
            "Set to a comma-separated list of allowed origins, e.g.: "
            "https://mumtaz.digital,https://app.mumtaz.digital"
        )
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8080",
                    "http://localhost:5173", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ── SQLite (local cache + non-Odoo users) ─────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

_USERS_DDL = """
    CREATE TABLE users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT    UNIQUE NOT NULL,
        password_hash TEXT,
        name          TEXT,
        company       TEXT,
        odoo_uid      INTEGER,
        tenant_id     INTEGER,
        plan          TEXT    DEFAULT 'trial',
        active        INTEGER DEFAULT 1,
        created_at    INTEGER DEFAULT (strftime('%s','now'))
    )
"""

_RESET_TOKENS_DDL = """
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token       TEXT    PRIMARY KEY,
        email       TEXT    NOT NULL,
        expires_at  INTEGER NOT NULL,
        used        INTEGER DEFAULT 0,
        created_at  INTEGER DEFAULT (strftime('%s','now'))
    )
"""

_STRIPE_EVENTS_DDL = """
    CREATE TABLE IF NOT EXISTS stripe_events (
        event_id   TEXT PRIMARY KEY,
        processed_at INTEGER DEFAULT (strftime('%s','now'))
    )
"""

_TENANTS_DDL = """
    CREATE TABLE IF NOT EXISTS tenants (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        db_name        TEXT    UNIQUE NOT NULL,
        odoo_url       TEXT    NOT NULL,
        company        TEXT    NOT NULL,
        admin_email    TEXT    NOT NULL,
        plan           TEXT    DEFAULT 'trial',
        status         TEXT    DEFAULT 'provisioning',
        error_msg      TEXT,
        custom_domain  TEXT,
        created_at     INTEGER DEFAULT (strftime('%s','now')),
        provisioned_at INTEGER
    )
"""

_PARTNERS_DDL = """
    CREATE TABLE IF NOT EXISTS partners (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        company       TEXT    NOT NULL,
        contact_name  TEXT    NOT NULL,
        email         TEXT    NOT NULL,
        phone         TEXT,
        country       TEXT,
        kind          TEXT,            -- bank, freezone, chamber, agency, enterprise, other
        clients       TEXT,            -- estimated client count: 1-50, 51-500, 500+
        domain        TEXT,            -- desired white-label domain
        notes         TEXT,
        status        TEXT    DEFAULT 'pending',  -- pending, approved, rejected
        created_at    INTEGER DEFAULT (strftime('%s','now'))
    )
"""

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute(f"CREATE TABLE IF NOT EXISTS users {_USERS_DDL.split('CREATE TABLE users')[1]}")

    # Detect old schema with NOT NULL on password_hash — recreate preserving data
    cols = {r[1]: r for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    need_rebuild = cols.get("password_hash") and cols["password_hash"][3]  # notnull flag
    if need_rebuild:
        logger.warning("[init_db] old schema detected — rebuilding users table")
        conn.execute("ALTER TABLE users RENAME TO users_old")
        conn.execute(_USERS_DDL)
        try:
            conn.execute("""
                INSERT INTO users (id, email, password_hash, name, company,
                                   odoo_uid, tenant_id, plan, active, created_at)
                SELECT id, email, password_hash,
                       COALESCE(name, ''), COALESCE(company, ''),
                       odoo_uid, tenant_id,
                       COALESCE(plan, 'trial'), COALESCE(active, 1),
                       COALESCE(created_at, strftime('%s','now'))
                FROM users_old
            """)
        except Exception as e:
            logger.error("[init_db] data migration error: %s", e)
        conn.execute("DROP TABLE IF EXISTS users_old")
    else:
        # Add any columns missing from older nullable schemas
        for col, defn in [
            ("name",      "TEXT"), ("company", "TEXT"),
            ("odoo_uid",  "INTEGER"), ("tenant_id", "INTEGER"),
            ("plan",      "TEXT DEFAULT 'trial'"),
            ("active",    "INTEGER DEFAULT 1"),
            ("created_at","INTEGER DEFAULT (strftime('%s','now'))"),
            ("onboarding_json", "TEXT"),
            ("role",           "TEXT"),
            ("erp_company_id", "INTEGER"),
            ("tenant_db",      "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except Exception:
                pass

    conn.execute(_RESET_TOKENS_DDL)
    conn.execute(_STRIPE_EVENTS_DDL)
    conn.execute(_PARTNERS_DDL)
    conn.execute(_TENANTS_DDL)
    # Migrate tenants table — add any missing columns
    for col, defn in [
        ("custom_domain", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE tenants ADD COLUMN {col} {defn}")
        except Exception:
            pass
    conn.commit()
    conn.close()

# ── JWT ───────────────────────────────────────────────────────────────
def make_token(user_id: int, email: str, extra: dict = None) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": int(time.time()) + 3600 * TOKEN_HOURS,
        "jti": _secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET, ALGO)

async def require_auth(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    try:
        return jwt.decode(authorization.split(" ", 1)[1], SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(401, f"Token invalid: {e}")

# ── Odoo XML-RPC ──────────────────────────────────────────────────────
class _TimeoutTransport(xmlrpc.client.Transport):
    """HTTP transport that enforces a socket timeout — without it,
    XML-RPC calls hang forever if Odoo becomes unreachable."""
    def __init__(self, timeout: int = 15):
        super().__init__()
        self._timeout = timeout
    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn

class _SafeTimeoutTransport(xmlrpc.client.SafeTransport):
    def __init__(self, timeout: int = 15):
        super().__init__()
        self._timeout = timeout
    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn

# Last connectivity error — surfaced via /health and /admin/odoo/status
_odoo_last_error: dict = {"at": None, "message": None, "ts": None}

def _record_odoo_error(where: str, exc: Exception) -> None:
    _odoo_last_error["at"]      = where
    _odoo_last_error["message"] = f"{type(exc).__name__}: {exc}"
    _odoo_last_error["ts"]      = int(time.time())
    logger.error("[Odoo] %s error: %s", where, exc)

def _odoo_transport():
    return (_SafeTimeoutTransport(ODOO_TIMEOUT)
            if ODOO_URL.lower().startswith("https")
            else _TimeoutTransport(ODOO_TIMEOUT))

def _odoo_common():
    return xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/common", allow_none=True, transport=_odoo_transport(),
    )

def _odoo_object():
    return xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object", allow_none=True, transport=_odoo_transport(),
    )

def odoo_server_info() -> dict:
    """Returns Odoo version metadata. Doesn't require auth."""
    try:
        info = _odoo_common().version()
        return {
            "server_version":   info.get("server_version"),
            "server_serie":     info.get("server_serie"),
            "protocol_version": info.get("protocol_version"),
        }
    except Exception as e:
        _record_odoo_error("version", e)
        return {}

def odoo_get_admin_uid(db: str = None) -> int | None:
    _db = db or ODOO_DB
    try:
        uid = _odoo_common().authenticate(_db, ODOO_ADMIN, ODOO_PASS, {})
        return uid if uid else None
    except Exception as e:
        _record_odoo_error("admin_auth", e)
        return None

def odoo_authenticate(email: str, password: str, db: str = None) -> int | None:
    """Returns Odoo UID on success, None on failure. Uses tenant DB when provided."""
    _db = db or ODOO_DB
    try:
        uid = _odoo_common().authenticate(_db, email, password, {})
        return uid if uid else None
    except Exception as e:
        _record_odoo_error("user_auth", e)
        return None

def odoo_create_user(name: str, email: str, password: str, db: str = None) -> int | None:
    """Create an Odoo user in the given DB (defaults to shared admin DB)."""
    _db = db or ODOO_DB
    admin_uid = odoo_get_admin_uid(_db)
    if not admin_uid:
        logger.error("[Odoo] cannot create user in %s — admin auth failed", _db)
        return None
    try:
        obj = _odoo_object()
        user_id = obj.execute_kw(
            _db, admin_uid, ODOO_PASS, "res.users", "create", [{
                "name":     name,
                "login":    email,
                "email":    email,
                "password": password,
            }]
        )
        return user_id
    except Exception as e:
        _record_odoo_error("create_user", e)
        return None

def odoo_set_password(odoo_uid: int, new_password: str, db: str = None) -> bool:
    """Update an Odoo user's password in the tenant DB."""
    _db = db or ODOO_DB
    admin_uid = odoo_get_admin_uid(_db)
    if not admin_uid or not odoo_uid:
        return False
    try:
        _odoo_object().execute_kw(
            _db, admin_uid, ODOO_PASS, "res.users", "write",
            [[int(odoo_uid)], {"password": new_password}],
        )
        return True
    except Exception as e:
        _record_odoo_error("set_password", e)
        return False

def odoo_read_user(odoo_uid: int, db: str = None) -> dict:
    _db = db or ODOO_DB
    admin_uid = odoo_get_admin_uid(_db)
    if not admin_uid or not odoo_uid:
        return {}
    try:
        rows = _odoo_object().execute_kw(
            _db, admin_uid, ODOO_PASS, "res.users", "read",
            [[odoo_uid]], {"fields": ["name", "email", "login"]}
        )
        return rows[0] if rows else {}
    except Exception as e:
        _record_odoo_error("read_user", e)
        return {}

def _odoo_create_saas_invoice(email: str, name: str | None, plan_key: str, db: str = None) -> int | None:
    """Create and post an Odoo customer invoice for a SaaS plan change.

    - Non-blocking caller: always returns (None on any error, int on success).
    - Skips free/trial plans (price == 0).
    - Finds or creates the res.partner by email.
    - Finds or creates a service product per plan.
    - Applies the first 15% sale tax found (ZATCA VAT), posts the invoice.
    """
    plan = PLANS.get(plan_key)
    if not plan or plan.get("price", 0) == 0:
        return None
    _db = db or ODOO_DB
    admin_uid = odoo_get_admin_uid(_db)
    if not admin_uid:
        logger.error("[Invoice] Odoo admin auth failed — cannot create invoice for %s", email)
        return None
    try:
        obj = _odoo_object()

        # ── partner ──────────────────────────────────────────────────
        pids = obj.execute_kw(_db, admin_uid, ODOO_PASS, "res.partner", "search",
                              [[["email", "=", email]]], {"limit": 1})
        if pids:
            partner_id = pids[0]
        else:
            partner_id = obj.execute_kw(_db, admin_uid, ODOO_PASS, "res.partner", "create", [{
                "name": name or email,
                "email": email,
                "customer_rank": 1,
            }])

        # ── product ───────────────────────────────────────────────────
        product_name = f"Mumtaz {plan['name']} Plan"
        prods = obj.execute_kw(_db, admin_uid, ODOO_PASS, "product.product", "search",
                               [[["name", "=", product_name]]], {"limit": 1})
        product_id = prods[0] if prods else obj.execute_kw(
            _db, admin_uid, ODOO_PASS, "product.product", "create", [{
                "name": product_name, "type": "service",
                "sale_ok": True, "purchase_ok": False,
            }]
        )

        # ── 15% VAT tax ───────────────────────────────────────────────
        tax_ids = obj.execute_kw(_db, admin_uid, ODOO_PASS, "account.tax", "search",
                                 [[["amount", "=", 15.0], ["type_tax_use", "=", "sale"],
                                   ["active", "=", True]]], {"limit": 1})
        tax_cmd = [(6, 0, tax_ids)] if tax_ids else []

        # ── invoice ───────────────────────────────────────────────────
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        inv_id = obj.execute_kw(_db, admin_uid, ODOO_PASS, "account.move", "create", [{
            "move_type":  "out_invoice",
            "partner_id": partner_id,
            "invoice_date": today,
            "ref": f"SAAS-{plan_key.upper()}-{email[:30]}",
            "invoice_line_ids": [(0, 0, {
                "name":       f"Mumtaz {plan['name']} — monthly SaaS subscription",
                "product_id": product_id,
                "quantity":   1.0,
                "price_unit": float(plan["price"]),
                **({"tax_ids": tax_cmd} if tax_cmd else {}),
            })],
        }])
        obj.execute_kw(_db, admin_uid, ODOO_PASS, "account.move", "action_post", [[inv_id]])
        logger.info("[Invoice] #%s created → %s %s %s %s", inv_id, email, plan['name'], plan['price'], plan['currency'])
        return inv_id
    except Exception as e:
        _record_odoo_error("create_saas_invoice", e)
        logger.error("[Invoice] Failed for %s: %s", email, e)
        return None

def _make_tenant_code(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", company.lower())[:8] or "co"
    suffix = str(int(time.time()))[-5:]
    code = slug + suffix          # e.g. "acme12345" — satisfies [a-z0-9]{3-30}
    return code[:30]

def odoo_create_tenant(company: str, admin_email: str, admin_name: str, db: str = None) -> int | None:
    """Create a mumtaz.tenant record in the given DB. Returns tenant ID or None."""
    _db = db or ODOO_DB
    admin_uid = odoo_get_admin_uid(_db)
    if not admin_uid:
        return None
    try:
        obj  = _odoo_object()
        code = _make_tenant_code(company)

        bundles = obj.execute_kw(
            _db, admin_uid, ODOO_PASS, "mumtaz.module.bundle", "search",
            [[]], {"limit": 1}
        )
        bundle_id = bundles[0] if bundles else False

        tenant_id = obj.execute_kw(
            _db, admin_uid, ODOO_PASS, "mumtaz.tenant", "create", [{
                "name":          company,
                "code":          code,
                "database_name": _db,
                "admin_email":   admin_email,
                "admin_name":    admin_name,
                "bundle_id":     bundle_id,
                "state":         "draft",
            }]
        )
        return tenant_id
    except Exception as e:
        logger.error("[Odoo] create tenant error in %s: %s", _db, e)
        return None

def odoo_read_tenant(tenant_id: int) -> dict:
    admin_uid = odoo_get_admin_uid()
    if not admin_uid or not tenant_id:
        return {}
    try:
        rows = _odoo_object().execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "mumtaz.tenant", "read",
            [[tenant_id]],
            {"fields": ["name", "code", "state", "subscription_start",
                        "subscription_end", "admin_email", "database_name"]}
        )
        if not rows:
            return {}
        r = rows[0]
        # Flatten Many2one tuples
        return {k: (v[1] if isinstance(v, (list, tuple)) and len(v) == 2 else v)
                for k, v in r.items()}
    except Exception:
        return {}

# ── Module map: portal_id → Odoo technical name ───────────────────────
MODULE_MAP = {
    "crm":             "crm",
    "invoicing":       "account",
    "accounting":      "account_accountant",
    "inventory":       "stock",
    "purchase":        "purchase",
    "hr":              "hr",
    "project":         "project",
    "expenses":        "hr_expense",
    "timesheets":      "hr_timesheet",
    "mrp":             "mrp",
    "pos":             "point_of_sale",
    "ecommerce":       "website_sale",
    "helpdesk":        "helpdesk",
    "email_marketing": "mass_mailing",
}
INSTALLED_STATES = {"installed", "to install", "to upgrade"}

def odoo_get_module_states() -> dict:
    admin_uid = odoo_get_admin_uid()
    if not admin_uid:
        return {}
    try:
        rows = _odoo_object().execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "ir.module.module", "search_read",
            [[["name", "in", list(MODULE_MAP.values())]]],
            {"fields": ["name", "state"]}
        )
        name_to_state = {r["name"]: r["state"] for r in rows}
        return {
            portal_id: name_to_state.get(odoo_name, "uninstalled") in INSTALLED_STATES
            for portal_id, odoo_name in MODULE_MAP.items()
        }
    except Exception as e:
        logger.error("[modules] get states error: %s", e)
        return {}

def odoo_toggle_module(portal_id: str, install: bool) -> bool:
    odoo_name = MODULE_MAP.get(portal_id)
    if not odoo_name:
        return False
    admin_uid = odoo_get_admin_uid()
    if not admin_uid:
        return False
    try:
        obj = _odoo_object()
        ids = obj.execute_kw(ODOO_DB, admin_uid, ODOO_PASS, "ir.module.module", "search",
                             [[["name", "=", odoo_name]]])
        if not ids:
            return False
        method = "button_immediate_install" if install else "button_immediate_uninstall"
        obj.execute_kw(ODOO_DB, admin_uid, ODOO_PASS, "ir.module.module", method, [ids])
        return True
    except Exception as e:
        logger.error("[modules] toggle error (%s, install=%s): %s", portal_id, install, e)
        return False

# ── Pydantic models ───────────────────────────────────────────────────
class SignupReq(BaseModel):
    name: str
    email: str
    company: str = ""
    password: str

class RegisterReq(BaseModel):
    """Alias schema used by ZAKI CFO frontend (company is optional)."""
    name: str
    email: str
    company: str | None = None
    password: str

class LoginReq(BaseModel):
    email: str
    password: str

class ChatReq(BaseModel):
    message: str
    context: str = ""
    session_id: str | None = None

# ── Routes ────────────────────────────────────────────────────────────
@app.get("/health")
@app.get("/api/v1/health")
def health():
    """Liveness + Odoo connectivity probe. Mounted at both /health and
    /api/v1/health (the deploy script smoke-checks the latter)."""
    info      = odoo_server_info()
    admin_uid = odoo_get_admin_uid() if info else None
    return {
        "status":         "ok",
        "ai_ready":       bool(ANT_KEY),
        "odoo_live":      bool(admin_uid),
        "odoo_url":       ODOO_URL,
        "odoo_db":        ODOO_DB,
        "odoo_version":   info.get("server_version"),
        "odoo_serie":     info.get("server_serie"),
        "odoo_last_error": _odoo_last_error.get("message") if not admin_uid else None,
    }

def _provision_tenant_bg(user_id: int, company: str, email: str,
                         name: str, password: str) -> None:
    """
    Background task: provision an isolated Odoo DB, create user, update registry.
    Runs after the signup response is already sent to the client.
    """
    from provisioning import provision_tenant as _provision
    db = get_db()
    try:
        result = _provision(company, email)

        if not result["ok"]:
            # Record failure in tenants table
            db.execute(
                "INSERT OR REPLACE INTO tenants "
                "(db_name, odoo_url, company, admin_email, status, error_msg) "
                "VALUES (?, ?, ?, ?, 'error', ?)",
                (result["db_name"], ODOO_URL, company, email, result["error"])
            )
            db.commit()
            logger.error("[provision] FAILED for %s: %s", email, result['error'])
            return

        db_name = result["db_name"]

        # Create the human admin user in the new tenant DB
        uid = odoo_create_user(name, email, password, db=db_name)

        # Create mumtaz.tenant record in the new DB (non-fatal)
        tenant_id = None
        try:
            tenant_id = odoo_create_tenant(company, email, name, db=db_name)
        except Exception as exc:
            logger.warning("[provision] mumtaz.tenant record skipped: %s", exc)

        # Record active tenant
        db.execute(
            "INSERT OR REPLACE INTO tenants "
            "(db_name, odoo_url, company, admin_email, plan, status, provisioned_at) "
            "VALUES (?, ?, ?, ?, 'trial', 'active', strftime('%s','now'))",
            (db_name, ODOO_URL, company, email)
        )
        db.execute(
            "UPDATE users SET tenant_db=?, odoo_uid=?, tenant_id=? WHERE id=?",
            (db_name, uid, tenant_id, user_id)
        )
        db.commit()
        logger.info("[provision] SUCCESS for %s: db=%s", email, db_name)

    except Exception as exc:
        logger.exception("[provision] EXCEPTION for %s", email)
        try:
            db.execute(
                "INSERT OR REPLACE INTO tenants "
                "(db_name, odoo_url, company, admin_email, status, error_msg) "
                "VALUES (?, ?, ?, ?, 'error', ?)",
                (f"mt_unknown_{user_id}", ODOO_URL, company, email, str(exc))
            )
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


@app.post("/api/v1/auth/signup")
def signup(req: SignupReq, background_tasks: BackgroundTasks):
    email = req.email.strip().lower()
    db    = get_db()

    if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        db.close()
        raise HTTPException(400, "An account with this email already exists.")

    # 1. Reserve user record immediately — tenant DB provisioned in background
    ph = _hash_pw(req.password)
    db.execute(
        "INSERT INTO users (email, password_hash, name, company, plan, active) "
        "VALUES (?, ?, ?, ?, 'trial', 1)",
        (email, ph, req.name, req.company)
    )
    db.commit()
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    db.close()
    user_id = row["id"]

    # 2. Provision Odoo DB in background (30-60 s, non-blocking)
    background_tasks.add_task(
        _provision_tenant_bg, user_id, req.company, email, req.name, req.password
    )

    # 3. Welcome email
    try:
        subject, html, text = mailer.welcome_email(req.name, email)
        background_tasks.add_task(mailer.send_email, email, subject, html, text)
    except Exception:
        pass

    # 4. Return provisional token — odoo_db will be added once status=active
    token = make_token(user_id, email, {
        "name":    req.name,
        "company": req.company,
        "plan":    "trial",
        "status":  "provisioning",
    })
    return {
        "access_token": token,
        "token_type":   "bearer",
        "status":       "provisioning",
        "message":      "Your workspace is being set up. Poll /api/v1/tenant/status for readiness.",
        "user": {
            "name":    req.name,
            "email":   email,
            "company": req.company,
            "plan":    "trial",
        },
    }


@app.get("/api/v1/tenant/status")
async def tenant_status(auth: dict = Depends(require_auth)):
    """
    Poll this after signup to know when the tenant DB is ready.
    Once status='active', a fresh JWT with odoo_db is returned.
    """
    db  = get_db()
    row = db.execute(
        "SELECT id, name, company, plan, odoo_uid, tenant_id, tenant_db FROM users WHERE email=?",
        (auth["email"],)
    ).fetchone()
    db.close()

    if not row:
        raise HTTPException(404, "User not found")

    tenant_db = row["tenant_db"]

    if not tenant_db:
        return {"status": "provisioning", "odoo_db": None}

    # Check the tenants registry
    db  = get_db()
    rec = db.execute(
        "SELECT status, error_msg FROM tenants WHERE db_name=?", (tenant_db,)
    ).fetchone()
    db.close()

    if not rec:
        return {"status": "provisioning", "odoo_db": None}

    if rec["status"] == "active":
        fresh_token = make_token(row["id"], auth["email"], {
            "name":      row["name"]      or "",
            "company":   row["company"]   or "",
            "odoo_uid":  row["odoo_uid"],
            "tenant_id": row["tenant_id"],
            "plan":      row["plan"]      or "trial",
            "odoo_db":   tenant_db,
        })
        return {
            "status":       "active",
            "odoo_db":      tenant_db,
            "access_token": fresh_token,
        }

    return {"status": rec["status"], "odoo_db": None, "error": rec["error_msg"]}

# ── ERP (Odoo) product catalogue ─────────────────────────────────────
def _user_tenant_and_products(email: str) -> tuple[str | None, list[str]]:
    """Return (tenant_db, enabled_product_keys) for a user."""
    import json as _json
    db  = get_db()
    row = db.execute(
        "SELECT tenant_db, onboarding_json FROM users WHERE email = ?", (email,)
    ).fetchone()
    db.close()
    if not row:
        return None, []
    products: list[str] = []
    if row["onboarding_json"]:
        try:
            products = (_json.loads(row["onboarding_json"]) or {}).get("products", []) or []
        except Exception:
            products = []
    return row["tenant_db"], products


@app.get("/api/v1/erp/products")
async def erp_products(auth: dict = Depends(require_auth)):
    """
    List the tenant's sellable products from their isolated Odoo ERP DB so a
    vendor can import them as marketplace listings.

    Returns erp_enabled=False (never an error) when the tenant has no
    provisioned ERP DB or ERP is not part of their onboarding/plan. Every
    query is scoped to the tenant's own Odoo DB — no cross-tenant access.
    """
    tenant_db, products = _user_tenant_and_products(auth["email"])

    if not tenant_db or "erp" not in products:
        return {"erp_enabled": False, "products": []}

    try:
        admin_uid = odoo_get_admin_uid(db=tenant_db)
        if not admin_uid:
            return {"erp_enabled": True, "products": [], "error": "ERP unavailable"}

        obj  = _odoo_object()
        rows = obj.execute_kw(
            tenant_db, admin_uid, ODOO_PASS,
            "product.product", "search_read",
            [[["sale_ok", "=", True]]],
            {
                "fields": ["name", "default_code", "list_price",
                           "qty_available", "uom_id", "categ_id",
                           "description_sale"],
                "limit": 200,
                "order": "name asc",
            },
        )
    except Exception as e:
        _record_odoo_error("erp_products", e)
        # Never surface internal errors to the client.
        return {"erp_enabled": True, "products": [], "error": "Could not reach ERP"}

    def _m2o(v):  # Odoo many2one comes back as [id, "name"] or False
        return v[1] if isinstance(v, (list, tuple)) and len(v) == 2 else None

    out = [{
        "erp_id":      r.get("id"),
        "name":        r.get("name") or "",
        "sku":         r.get("default_code") or "",
        "price":       r.get("list_price") or 0,
        "uom":         _m2o(r.get("uom_id")) or "Unit",
        "category":    _m2o(r.get("categ_id")) or "Uncategorised",
        "qty":         r.get("qty_available") or 0,
        "description": r.get("description_sale") or "",
    } for r in rows]

    return {"erp_enabled": True, "products": out}


# ── ERP → Marketplace listings (real Odoo records) ───────────────────
def _erp_default_category(obj, db: str, uid: int, name: str = "General") -> int:
    ids = obj.execute_kw(db, uid, ODOO_PASS, "mumtaz.marketplace.category", "search",
                         [[["name", "=", name]]], {"limit": 1})
    if ids:
        return ids[0]
    return obj.execute_kw(db, uid, ODOO_PASS, "mumtaz.marketplace.category", "create",
                          [{"name": name, "sequence": 10}])


@app.get("/api/v1/erp/listings")
async def erp_listings(auth: dict = Depends(require_auth)):
    """Return the tenant's existing marketplace listings from their Odoo DB."""
    tenant_db, _ = _user_tenant_and_products(auth["email"])
    if not tenant_db:
        return {"enabled": False, "listings": []}
    try:
        uid = odoo_get_admin_uid(db=tenant_db)
        if not uid:
            return {"enabled": True, "listings": [], "error": "ERP unavailable"}
        obj  = _odoo_object()
        rows = obj.execute_kw(
            tenant_db, uid, ODOO_PASS, "mumtaz.marketplace.listing", "search_read",
            [[]],
            {"fields": ["name", "category_id", "price", "currency_id", "state",
                        "listing_type", "min_order_qty", "lead_time_days", "inquiry_count"],
             "limit": 200, "order": "id desc"},
        )
    except Exception as e:
        _record_odoo_error("erp_listings", e)
        return {"enabled": True, "listings": [], "error": "Could not reach ERP"}

    def _m2o(v):
        return v[1] if isinstance(v, (list, tuple)) and len(v) == 2 else None

    out = [{
        "id":        r.get("id"),
        "name":      r.get("name") or "",
        "category":  _m2o(r.get("category_id")) or "Uncategorised",
        "price":     r.get("price") or 0,
        "currency":  _m2o(r.get("currency_id")) or "AED",
        "state":     r.get("state") or "draft",
        "type":      r.get("listing_type") or "product",
        "moq":       r.get("min_order_qty") or 0,
        "lead_days": r.get("lead_time_days") or 0,
        "inquiries": r.get("inquiry_count") or 0,
    } for r in rows]
    return {"enabled": True, "listings": out}


class ImportListingsReq(BaseModel):
    product_ids: list[int]
    moq: float = 1.0
    lead_days: int = 7

@app.post("/api/v1/erp/listings/import")
async def erp_import_listings(req: ImportListingsReq, auth: dict = Depends(require_auth)):
    """
    Create marketplace listings (mumtaz.marketplace.listing) from selected
    Odoo products. Tenant-scoped to the caller's Odoo DB; re-reads product
    data server-side (never trusts client prices); dedupes by product
    template so re-importing won't create duplicates.
    """
    tenant_db, products = _user_tenant_and_products(auth["email"])
    if not tenant_db or "erp" not in products:
        raise HTTPException(409, "ERP is not enabled for this account")
    if not req.product_ids:
        raise HTTPException(400, "No products selected")

    try:
        uid = odoo_get_admin_uid(db=tenant_db)
        if not uid:
            raise RuntimeError("no admin uid for tenant db")
        obj   = _odoo_object()
        prods = obj.execute_kw(
            tenant_db, uid, ODOO_PASS, "product.product", "read",
            [req.product_ids[:200]],
            {"fields": ["name", "default_code", "list_price",
                        "description_sale", "product_tmpl_id"]},
        )
        cat_id = _erp_default_category(obj, tenant_db, uid)

        created, skipped = 0, 0
        for p in prods:
            tmpl    = p.get("product_tmpl_id")
            tmpl_id = tmpl[0] if isinstance(tmpl, (list, tuple)) else None
            if tmpl_id:
                dup = obj.execute_kw(tenant_db, uid, ODOO_PASS, "mumtaz.marketplace.listing",
                                     "search", [[["product_tmpl_id", "=", tmpl_id]]], {"limit": 1})
                if dup:
                    skipped += 1
                    continue
            name = p.get("name") or "Product"
            desc = p.get("description_sale") or name
            vals = {
                "name":              name,
                "category_id":       cat_id,
                "listing_type":      "product",
                "state":             "draft",
                "short_description": (desc[:120] if isinstance(desc, str) else name),
                "description":       f"<p>{desc}</p>",
                "price":             p.get("list_price") or 0.0,
                "price_type":        "fixed",
                "min_order_qty":     req.moq,
                "lead_time_days":    req.lead_days,
            }
            if tmpl_id:
                vals["product_tmpl_id"] = tmpl_id
            obj.execute_kw(tenant_db, uid, ODOO_PASS, "mumtaz.marketplace.listing", "create", [vals])
            created += 1
    except HTTPException:
        raise
    except Exception as e:
        _record_odoo_error("erp_import_listings", e)
        raise HTTPException(502, "Could not import products into the marketplace. Please try again.")

    return {"ok": True, "created": created, "skipped": skipped}


# ── Public marketplace feed (published listings across tenants) ──────
_PUBLIC_LISTINGS_CACHE: dict = {"ts": 0.0, "data": []}
_PUBLIC_LISTINGS_TTL = 120  # seconds — avoid querying every tenant DB per hit

@app.get("/api/v1/marketplace/public/listings")
def public_marketplace_listings():
    """
    Public (no auth): PUBLISHED marketplace listings aggregated across active
    tenants, for the marketplace.mumtaz.digital homepage. Only published
    records and public fields are returned. Cached briefly so a page view
    doesn't fan out to every tenant DB.
    """
    now = time.time()
    if (now - _PUBLIC_LISTINGS_CACHE["ts"]) < _PUBLIC_LISTINGS_TTL and _PUBLIC_LISTINGS_CACHE["data"]:
        return {"listings": _PUBLIC_LISTINGS_CACHE["data"], "cached": True}

    db = get_db()
    tenant_dbs = [r["db_name"] for r in db.execute(
        "SELECT db_name FROM tenants WHERE status='active'").fetchall()]
    db.close()

    def _m2o(v):
        return v[1] if isinstance(v, (list, tuple)) and len(v) == 2 else None

    out = []
    for tdb in tenant_dbs[:100]:
        try:
            uid = odoo_get_admin_uid(db=tdb)
            if not uid:
                continue
            obj  = _odoo_object()
            rows = obj.execute_kw(
                tdb, uid, ODOO_PASS, "mumtaz.marketplace.listing", "search_read",
                [[["state", "=", "published"]]],
                {"fields": ["name", "category_id", "price", "currency_id",
                            "short_description", "listing_type", "min_order_qty",
                            "lead_time_days", "company_id"],
                 "limit": 50, "order": "id desc"},
            )
        except Exception as e:
            _record_odoo_error("public_listings", e)
            continue
        for r in rows:
            out.append({
                "name":      r.get("name") or "",
                "company":   _m2o(r.get("company_id")) or "Verified Supplier",
                "category":  _m2o(r.get("category_id")) or "General",
                "price":     r.get("price") or 0,
                "currency":  _m2o(r.get("currency_id")) or "AED",
                "summary":   r.get("short_description") or "",
                "type":      r.get("listing_type") or "product",
                "moq":       r.get("min_order_qty") or 0,
                "lead_days": r.get("lead_time_days") or 0,
            })

    _PUBLIC_LISTINGS_CACHE.update({"ts": now, "data": out})
    return {"listings": out, "cached": False}


@app.get("/api/v1/tenant/invoices")
async def tenant_invoices(auth: dict = Depends(require_auth)):
    """
    The tenant's OWN customer invoices from their Odoo (account.move,
    out_invoice): a summary (total invoiced / paid / outstanding / count) plus
    the most recent invoices. Tenant-scoped; fails soft if the ERP is
    unprovisioned or unreachable so the console always renders.
    """
    tenant_db, _ = _user_tenant_and_products(auth["email"])
    if not tenant_db:
        return {"provisioned": False, "reachable": False, "currency": "AED",
                "summary": {"total": 0, "paid": 0, "due": 0, "count": 0}, "invoices": []}
    try:
        uid = odoo_get_admin_uid(db=tenant_db)
        if not uid:
            return {"provisioned": True, "reachable": False, "currency": "AED",
                    "summary": {"total": 0, "paid": 0, "due": 0, "count": 0}, "invoices": []}
        obj  = _odoo_object()
        rows = obj.execute_kw(
            tenant_db, uid, ODOO_PASS, "account.move", "search_read",
            [[["move_type", "=", "out_invoice"]]],
            {"fields": ["name", "invoice_date", "amount_total", "amount_residual",
                        "state", "payment_state", "partner_id", "currency_id"],
             "limit": 50, "order": "invoice_date desc, id desc"},
        )
        grp = obj.execute_kw(
            tenant_db, uid, ODOO_PASS, "account.move", "read_group",
            [[["move_type", "=", "out_invoice"], ["state", "=", "posted"]]],
            ["amount_total:sum", "amount_residual:sum"], [],
        )
        currency = "AED"
        try:
            comp = obj.execute_kw(tenant_db, uid, ODOO_PASS, "res.company", "search_read",
                                  [[]], {"fields": ["currency_id"], "limit": 1})
            if comp and comp[0].get("currency_id"):
                currency = comp[0]["currency_id"][1]
        except Exception:
            pass
    except Exception as e:
        _record_odoo_error("tenant_invoices", e)
        return {"provisioned": True, "reachable": False, "currency": "AED",
                "summary": {"total": 0, "paid": 0, "due": 0, "count": 0}, "invoices": []}

    def _m2o(v):
        return v[1] if isinstance(v, (list, tuple)) and len(v) == 2 else None

    total = (grp[0].get("amount_total")    if grp else 0) or 0
    due   = (grp[0].get("amount_residual") if grp else 0) or 0
    count = (grp[0].get("__count")         if grp else 0) or 0

    invoices = [{
        "number":        r.get("name") or "Draft",
        "partner":       _m2o(r.get("partner_id")) or "—",
        "date":          r.get("invoice_date") or "",
        "total":         r.get("amount_total") or 0,
        "due":           r.get("amount_residual") or 0,
        "currency":      _m2o(r.get("currency_id")) or currency,
        "state":         r.get("state") or "draft",
        "payment_state": r.get("payment_state") or "not_paid",
    } for r in rows]

    return {
        "provisioned": True, "reachable": True, "currency": currency,
        "summary": {"total": round(total, 2), "paid": round(total - due, 2),
                    "due": round(due, 2), "count": count},
        "invoices": invoices,
    }


# ── Tenant app enable/disable (control-plane feature toggles) ─────────
# Maps the portal's app cards to mumtaz.feature codes. Enabling an app
# writes a force_on tenant override; disabling writes force_off. This is
# non-destructive (no Odoo module install/uninstall) and instant.
APP_FEATURES = {
    "erp":         {"code": "erp_access",         "name": "Mumtaz ERP",      "area": "erp"},
    "zaki":        {"code": "zaki_access",        "name": "ZAKI AI Agents",  "area": "ai"},
    "marketplace": {"code": "marketplace_access", "name": "B2B Marketplace", "area": "marketplace"},
}

# ERP sub-modules — itemized inside the ERP app, gated per package. Each maps
# to a mumtaz.feature (area "erp"); enforcement hides the module's Odoo menus
# by revoking its user group (see mumtaz.erp.module.access). Accounting is the
# backbone (powers the Invoicing console + tenant-revenue figures).
ERP_MODULES = {
    "accounting":    {"code": "erp_accounting",    "name": "Accounting & Invoicing", "area": "erp"},
    "inventory":     {"code": "erp_inventory",     "name": "Inventory & Warehouse",  "area": "erp"},
    "sales":         {"code": "erp_sales",         "name": "Sales & CRM",            "area": "erp"},
    "hr":            {"code": "erp_hr",             "name": "HR & Payroll",          "area": "erp"},
    "manufacturing": {"code": "erp_manufacturing", "name": "Manufacturing",          "area": "erp"},
}

def _erp_find_tenant(obj, db: str, admin_uid: int, create: bool = False) -> int | None:
    """Resolve (optionally create) the mumtaz.tenant record inside a tenant DB."""
    ids = obj.execute_kw(db, admin_uid, ODOO_PASS, "mumtaz.tenant", "search",
                         [[["database_name", "=", db]]], {"limit": 1})
    if not ids:
        ids = obj.execute_kw(db, admin_uid, ODOO_PASS, "mumtaz.tenant", "search", [[]], {"limit": 1})
    if ids:
        return ids[0]
    if not create:
        return None
    code = (re.sub(r"[^a-z0-9]+", "", db.lower())[:32] or "tenant")
    return obj.execute_kw(db, admin_uid, ODOO_PASS, "mumtaz.tenant", "create",
        [{"name": db, "code": code, "database_name": db, "state": "active"}])

def _enforce_marketplace_access(obj, db: str, admin_uid: int, code: str, enabled: bool) -> None:
    """When the marketplace app is toggled, grant/revoke the Odoo Marketplace
    User group so the change is enforced server-side (not just hidden in the
    portal). Best-effort — never blocks the toggle if the addon is absent."""
    if code != "marketplace_access":
        return
    try:
        obj.execute_kw(db, admin_uid, ODOO_PASS,
                       "mumtaz.marketplace.access", "set_access", [bool(enabled)])
    except Exception as e:
        _record_odoo_error("marketplace_access_sync", e)


def _enforce_module_access(obj, db: str, admin_uid: int, module_key: str, enabled: bool) -> None:
    """Show/hide an ERP module's Odoo menus by syncing its user group.
    Best-effort — never blocks the toggle if the addon/group is absent."""
    try:
        obj.execute_kw(db, admin_uid, ODOO_PASS,
                       "mumtaz.erp.module.access", "set_module_access",
                       [module_key, bool(enabled)])
    except Exception as e:
        _record_odoo_error("module_access_sync", e)


def _erp_find_feature(obj, db: str, admin_uid: int, spec: dict, create: bool = False) -> int | None:
    """Resolve (optionally create) a mumtaz.feature by code inside a tenant DB."""
    ids = obj.execute_kw(db, admin_uid, ODOO_PASS, "mumtaz.feature", "search",
                         [[["code", "=", spec["code"]]]], {"limit": 1})
    if ids:
        return ids[0]
    if not create:
        return None
    return obj.execute_kw(db, admin_uid, ODOO_PASS, "mumtaz.feature", "create",
        [{"code": spec["code"], "name": spec["name"], "product_area": spec["area"],
          "feature_type": "toggle", "is_customer_visible": True}])


@app.get("/api/v1/tenant/features")
async def get_tenant_features(auth: dict = Depends(require_auth)):
    """
    Return enable/disable state of each Mumtaz app for the caller's tenant.
    Apps are ON by default unless explicitly force_off in the tenant's Odoo
    control plane. Fails open (everything enabled) when the ERP/control plane
    is not yet provisioned — never errors.
    """
    plan      = _user_plan(auth["email"])
    incl      = _plan_apps(plan)

    def _all_enabled(provisioned: bool):
        return {"provisioned": provisioned, "plan": plan, "apps": [
            {"key": k, "code": s["code"], "name": s["name"], "area": s["area"],
             "enabled": k in incl, "included": k in incl}
            for k, s in APP_FEATURES.items()
        ]}

    tenant_db, _ = _user_tenant_and_products(auth["email"])
    if not tenant_db:
        return _all_enabled(False)

    try:
        admin_uid = odoo_get_admin_uid(db=tenant_db)
        if not admin_uid:
            return _all_enabled(False)
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, tenant_db, admin_uid, create=False)
        if not tenant_id:
            return _all_enabled(False)

        codes = [s["code"] for s in APP_FEATURES.values()]
        feats = obj.execute_kw(tenant_db, admin_uid, ODOO_PASS, "mumtaz.feature",
                               "search_read", [[["code", "in", codes]]], {"fields": ["code"]})
        code_to_fid = {r["code"]: r["id"] for r in feats}
        fids = list(code_to_fid.values())
        modes: dict = {}
        if fids:
            ov = obj.execute_kw(tenant_db, admin_uid, ODOO_PASS, "mumtaz.tenant.feature",
                                "search_read",
                                [[["tenant_id", "=", tenant_id], ["feature_id", "in", fids]]],
                                {"fields": ["feature_id", "override_mode"]})
            modes = {r["feature_id"][0]: r["override_mode"] for r in ov}
    except Exception as e:
        _record_odoo_error("get_tenant_features", e)
        return _all_enabled(False)

    apps = []
    for k, s in APP_FEATURES.items():
        fid = code_to_fid.get(s["code"])
        mode = modes.get(fid) if fid else None
        included = k in incl
        # An app is on only if its package includes it AND it isn't force_off.
        apps.append({"key": k, "code": s["code"], "name": s["name"], "area": s["area"],
                     "included": included, "enabled": included and mode != "force_off"})
    return {"provisioned": True, "plan": plan, "apps": apps}


class FeatureToggleReq(BaseModel):
    code: str
    enabled: bool

@app.put("/api/v1/tenant/features")
async def set_tenant_feature(req: FeatureToggleReq, auth: dict = Depends(require_auth)):
    """
    Enable/disable a Mumtaz app for the caller's tenant by writing a
    force_on / force_off override in their isolated Odoo control plane.
    Tenant-scoped; find-or-creates the tenant + feature records as needed.
    """
    app_key = next((k for k, s in APP_FEATURES.items() if s["code"] == req.code), None)
    spec    = APP_FEATURES.get(app_key) if app_key else None
    if not spec:
        raise HTTPException(400, "Unknown feature")

    # Packages gate access: you can't enable an app your plan doesn't include.
    if req.enabled and app_key not in _plan_apps(_user_plan(auth["email"])):
        raise HTTPException(402, "Upgrade your package to enable this app")

    tenant_db, _ = _user_tenant_and_products(auth["email"])
    if not tenant_db:
        raise HTTPException(409, "ERP is not provisioned for this account yet")

    try:
        admin_uid = odoo_get_admin_uid(db=tenant_db)
        if not admin_uid:
            raise RuntimeError("no admin uid for tenant db")
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, tenant_db, admin_uid, create=True)
        fid       = _erp_find_feature(obj, tenant_db, admin_uid, spec, create=True)
        mode      = "force_on" if req.enabled else "force_off"

        existing = obj.execute_kw(tenant_db, admin_uid, ODOO_PASS, "mumtaz.tenant.feature",
                                  "search",
                                  [[["tenant_id", "=", tenant_id], ["feature_id", "=", fid]]],
                                  {"limit": 1})
        vals = {"override_mode": mode, "reason": "Set from Mumtaz portal app toggle."}
        if existing:
            obj.execute_kw(tenant_db, admin_uid, ODOO_PASS, "mumtaz.tenant.feature",
                           "write", [existing, vals])
        else:
            obj.execute_kw(tenant_db, admin_uid, ODOO_PASS, "mumtaz.tenant.feature",
                           "create", [{**vals, "tenant_id": tenant_id, "feature_id": fid}])
        _enforce_marketplace_access(obj, tenant_db, admin_uid, req.code, req.enabled)
    except HTTPException:
        raise
    except Exception as e:
        _record_odoo_error("set_tenant_feature", e)
        raise HTTPException(502, "Could not update the app in your ERP. Please try again.")

    return {"ok": True, "code": req.code, "enabled": req.enabled}


@app.get("/api/v1/tenant/modules")
async def get_tenant_modules(auth: dict = Depends(require_auth)):
    """ERP sub-modules for the caller's tenant, with package inclusion + state."""
    plan = _user_plan(auth["email"])
    incl = _plan_modules(plan)

    def _all(provisioned):
        return {"provisioned": provisioned, "plan": plan, "modules": [
            {"key": k, "code": s["code"], "name": s["name"],
             "included": k in incl, "enabled": k in incl}
            for k, s in ERP_MODULES.items()]}

    tenant_db, _ = _user_tenant_and_products(auth["email"])
    if not tenant_db:
        return _all(False)
    try:
        uid = odoo_get_admin_uid(db=tenant_db)
        if not uid:
            return _all(False)
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, tenant_db, uid, create=False)
        if not tenant_id:
            return _all(False)
        codes = [s["code"] for s in ERP_MODULES.values()]
        feats = obj.execute_kw(tenant_db, uid, ODOO_PASS, "mumtaz.feature", "search_read",
                               [[["code", "in", codes]]], {"fields": ["code"]})
        c2f = {r["code"]: r["id"] for r in feats}
        fids = list(c2f.values())
        modes = {}
        if fids:
            ov = obj.execute_kw(tenant_db, uid, ODOO_PASS, "mumtaz.tenant.feature", "search_read",
                                [[["tenant_id", "=", tenant_id], ["feature_id", "in", fids]]],
                                {"fields": ["feature_id", "override_mode"]})
            modes = {r["feature_id"][0]: r["override_mode"] for r in ov}
    except Exception as e:
        _record_odoo_error("get_tenant_modules", e)
        return _all(False)

    mods = []
    for k, s in ERP_MODULES.items():
        fid = c2f.get(s["code"])
        mode = modes.get(fid) if fid else None
        included = k in incl
        mods.append({"key": k, "code": s["code"], "name": s["name"],
                     "included": included, "enabled": included and mode != "force_off"})
    return {"provisioned": True, "plan": plan, "modules": mods}


class ModuleToggleReq(BaseModel):
    key: str
    enabled: bool

@app.put("/api/v1/tenant/modules")
async def set_tenant_module(req: ModuleToggleReq, auth: dict = Depends(require_auth)):
    """Enable/disable an ERP module for the caller's tenant (within their package)."""
    spec = ERP_MODULES.get(req.key)
    if not spec:
        raise HTTPException(400, "Unknown module")
    if req.enabled and req.key not in _plan_modules(_user_plan(auth["email"])):
        raise HTTPException(402, "Upgrade your package to enable this module")

    tenant_db, _ = _user_tenant_and_products(auth["email"])
    if not tenant_db:
        raise HTTPException(409, "ERP is not provisioned for this account yet")
    try:
        uid = odoo_get_admin_uid(db=tenant_db)
        if not uid:
            raise RuntimeError("no admin uid")
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, tenant_db, uid, create=True)
        fid       = _erp_find_feature(obj, tenant_db, uid, spec, create=True)
        mode      = "force_on" if req.enabled else "force_off"
        existing  = obj.execute_kw(tenant_db, uid, ODOO_PASS, "mumtaz.tenant.feature", "search",
                                   [[["tenant_id", "=", tenant_id], ["feature_id", "=", fid]]], {"limit": 1})
        vals = {"override_mode": mode, "reason": "Set from Mumtaz portal module toggle."}
        if existing:
            obj.execute_kw(tenant_db, uid, ODOO_PASS, "mumtaz.tenant.feature", "write", [existing, vals])
        else:
            obj.execute_kw(tenant_db, uid, ODOO_PASS, "mumtaz.tenant.feature", "create",
                           [{**vals, "tenant_id": tenant_id, "feature_id": fid}])
        _enforce_module_access(obj, tenant_db, uid, req.key, req.enabled)
    except HTTPException:
        raise
    except Exception as e:
        _record_odoo_error("set_tenant_module", e)
        raise HTTPException(502, "Could not update the module in your ERP. Please try again.")
    return {"ok": True, "key": req.key, "enabled": req.enabled}

class ForgotReq(BaseModel):
    email: str

class ResetReq(BaseModel):
    token: str
    password: str

RESET_TOKEN_TTL_SECS = 3600  # 1 hour

def portal_base_url() -> str:
    return settings.get("PORTAL_BASE_URL", "https://app.mumtaz.digital") or "https://app.mumtaz.digital"

# Backwards-compat shim — anything that did `f"{PORTAL_BASE_URL}/..."` keeps working.
PORTAL_BASE_URL = portal_base_url()

# Platform owners are always super-admins: they implicitly have admin access,
# cannot be removed through the UI, and can oversee every tenant. Configurable
# via the MUMTAZ_OWNERS setting (comma-separated); the founding owner is always
# included so the platform is never left without a super-admin.
DEFAULT_OWNER_EMAIL = "umer@mumtaz.digital"

def owner_emails() -> set[str]:
    """Live read of platform owners (super-admins). Always includes the founder."""
    raw = settings.get("MUMTAZ_OWNERS", "") or ""
    owners = {e.strip().lower() for e in raw.split(",") if e.strip()}
    owners.add(DEFAULT_OWNER_EMAIL)
    return owners

def admin_emails() -> set[str]:
    """Live read so admins added through the UI take effect immediately.
    Owners are always admins."""
    raw = settings.get("MUMTAZ_ADMINS", "") or ""
    admins = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return admins | owner_emails()

# Backwards-compat shim — modules importing ADMIN_EMAILS still see the env list.
ADMIN_EMAILS = admin_emails()

def require_admin(auth: dict = Depends(require_auth)) -> dict:
    email = (auth.get("email") or "").lower()
    if email not in admin_emails():
        raise HTTPException(403, "Admin access required.")
    # Confirm the account is still active (catches deactivated tokens within their TTL).
    db  = get_db()
    row = db.execute("SELECT active FROM users WHERE email=?", (email,)).fetchone()
    db.close()
    if row and not row["active"]:
        raise HTTPException(403, "Account is deactivated.")
    return auth

def require_owner(auth: dict = Depends(require_auth)) -> dict:
    """Gate owner-only actions (platform-wide oversight)."""
    email = (auth.get("email") or "").lower()
    if email not in owner_emails():
        raise HTTPException(403, "Owner access required.")
    return auth

@app.post("/api/v1/auth/forgot")
def forgot_password(req: ForgotReq, background_tasks: BackgroundTasks = None):
    """Initiate password reset. Always returns 200 to prevent email enumeration."""
    import secrets
    email = req.email.strip().lower()
    db    = get_db()
    row   = db.execute("SELECT name FROM users WHERE email=?", (email,)).fetchone()
    if row:
        token   = secrets.token_urlsafe(32)
        expires = int(time.time()) + RESET_TOKEN_TTL_SECS
        db.execute(
            "INSERT INTO password_reset_tokens (token, email, expires_at) VALUES (?, ?, ?)",
            (token, email, expires),
        )
        db.commit()
        if background_tasks is not None:
            reset_url = f"{PORTAL_BASE_URL}/reset.html?token={token}"
            subject, html, text = mailer.password_reset_email(row["name"] or "", reset_url)
            background_tasks.add_task(mailer.send_email, email, subject, html, text)
    db.close()
    # Always 200 — don't reveal whether the email is registered.
    return {"ok": True, "message": "If this email is registered, a reset link has been sent."}

@app.post("/api/v1/auth/reset")
def reset_password(req: ResetReq):
    """Consume a reset token and update the user's password.

    Updates BOTH the SQLite cache and the Odoo res.users record. Odoo is the
    source of truth for /auth/login, so skipping the Odoo write would leave
    users unable to log in with their new password."""
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    db  = get_db()
    row = db.execute(
        "SELECT email, expires_at, used FROM password_reset_tokens WHERE token=?",
        (req.token,),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(400, "Invalid or expired reset link.")
    if row["used"]:
        db.close()
        raise HTTPException(400, "This reset link has already been used.")
    if int(row["expires_at"]) < int(time.time()):
        db.close()
        raise HTTPException(400, "This reset link has expired. Request a new one.")

    user_row = db.execute(
        "SELECT id, odoo_uid FROM users WHERE email=?", (row["email"],)
    ).fetchone()

    new_hash = _hash_pw(req.password)
    db.execute("UPDATE users SET password_hash=? WHERE email=?", (new_hash, row["email"]))
    db.execute("UPDATE password_reset_tokens SET used=1 WHERE token=?", (req.token,))
    db.commit()
    db.close()

    # Push to Odoo so the user can actually log in. If Odoo is unreachable
    # we still return ok=True (the SQLite fallback path will let them in),
    # but report odoo_synced so the UI can surface a "try again later" hint.
    odoo_synced = False
    if user_row and user_row["odoo_uid"]:
        odoo_synced = odoo_set_password(int(user_row["odoo_uid"]), req.password)

    return {"ok": True, "odoo_synced": odoo_synced}

@app.post("/api/v1/auth/register")
def register(req: RegisterReq):
    """Alias for /auth/signup — accepts optional company for ZAKI CFO frontend."""
    return signup(SignupReq(
        name=req.name,
        email=req.email,
        company=req.company or "",
        password=req.password,
    ))

@app.post("/api/v1/auth/login")
def login(req: LoginReq):
    email = req.email.strip().lower()
    db    = get_db()

    try:
        # Resolve which Odoo DB to authenticate against
        _db_row = db.execute("SELECT tenant_db FROM users WHERE email=?", (email,)).fetchone()
        _tenant_db = _db_row["tenant_db"] if _db_row else None

        # Primary: validate against the tenant's Odoo DB (or shared DB if not yet provisioned)
        odoo_uid = odoo_authenticate(email, req.password, db=_tenant_db)

        if odoo_uid:
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not row:
                info = odoo_read_user(odoo_uid)
                db.execute(
                    "INSERT OR IGNORE INTO users (email, name, odoo_uid, plan) VALUES (?, ?, ?, ?)",
                    (email, info.get("name", email.split("@")[0]), odoo_uid, "growth")
                )
                db.commit()
                row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            else:
                db.execute("UPDATE users SET odoo_uid=? WHERE email=?", (odoo_uid, email))
                db.commit()
        else:
            # Fallback: local SQLite
            row = db.execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
            if not row or not row["password_hash"] or \
                    not _verify_pw(req.password, row["password_hash"]):
                db.close()
                raise HTTPException(401, detail="Invalid email or password.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[login] unexpected error")
        db.close()
        raise HTTPException(500, detail="An unexpected error occurred. Please try again.")

    if not row:
        db.close()
        raise HTTPException(401, detail="Invalid email or password.")

    db.close()
    token = make_token(row["id"], email, {
        "name":      row["name"]      or "",
        "company":   row["company"]   or "",
        "odoo_uid":  row["odoo_uid"],
        "tenant_id": row["tenant_id"],
        "plan":      row["plan"]      or "growth",
        "odoo_db":   row["tenant_db"],   # tenant's isolated Odoo DB name
    })
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "name":      row["name"]      or "",
            "email":     email,
            "company":   row["company"]   or "",
            "plan":      row["plan"]      or "growth",
            "odoo_uid":  row["odoo_uid"],
            "tenant_id": row["tenant_id"],
            "odoo_db":   row["tenant_db"],
        },
    }

@app.get("/api/v1/auth/me")
async def me(auth: dict = Depends(require_auth)):
    db  = get_db()
    row = db.execute("SELECT * FROM users WHERE email=?", (auth["email"],)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, detail="User not found.")
    email_l = (row["email"] or "").lower()
    return {
        "name":      row["name"],
        "email":     row["email"],
        "company":   row["company"],
        "plan":      row["plan"],
        "odoo_uid":  row["odoo_uid"],
        "tenant_id": row["tenant_id"],
        "is_admin":  email_l in admin_emails(),
        "is_owner":  email_l in owner_emails(),
    }

class OnboardingReq(BaseModel):
    industry: str | None = None
    products: list[str] = []
    agents:   list[str] = []
    modules:  list[str] = []
    teamSize: str | None = None
    role:     str | None = None
    completedAt: str | None = None

@app.post("/api/v1/onboarding")
async def save_onboarding(req: OnboardingReq, auth: dict = Depends(require_auth)):
    """Persist a user's onboarding preferences (industry, products, agents,
    modules, team size). Idempotent — overwrites previous selection."""
    import json as _json
    db = get_db()
    db.execute(
        "UPDATE users SET onboarding_json = ?, role = COALESCE(?, role) WHERE email = ?",
        (_json.dumps(req.model_dump()), req.role, auth["email"]),
    )
    db.commit()
    db.close()
    return {"ok": True}

@app.get("/api/v1/onboarding")
async def get_onboarding(auth: dict = Depends(require_auth)):
    """Return the user's saved onboarding preferences (or null)."""
    import json as _json
    db  = get_db()
    row = db.execute(
        "SELECT onboarding_json, role FROM users WHERE email = ?",
        (auth["email"],),
    ).fetchone()
    db.close()
    if not row or not row["onboarding_json"]:
        return {"onboarding": None, "role": row["role"] if row else None}
    try:
        return {
            "onboarding": _json.loads(row["onboarding_json"]),
            "role": row["role"],
        }
    except Exception:
        return {"onboarding": None, "role": row["role"]}

# ── Tenant Custom Domain ─────────────────────────────────────────────

_DOMAIN_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$"
)
_PORTAL_HOST = os.environ.get("PORTAL_HOST", "app.mumtaz.digital")

class DomainReq(BaseModel):
    domain: str

@app.get("/api/v1/tenant/domain")
async def get_tenant_domain(auth: dict = Depends(require_auth)):
    """Return the tenant's current custom domain and CNAME instructions."""
    db  = get_db()
    row = db.execute(
        "SELECT tenant_db FROM users WHERE email = ?", (auth["email"],)
    ).fetchone()
    db.close()

    tenant_db = row["tenant_db"] if row else None
    if not tenant_db:
        return {"custom_domain": None, "cname_target": _PORTAL_HOST, "status": "no_tenant"}

    db  = get_db()
    rec = db.execute(
        "SELECT custom_domain, status FROM tenants WHERE db_name = ?", (tenant_db,)
    ).fetchone()
    db.close()

    if not rec:
        return {"custom_domain": None, "cname_target": _PORTAL_HOST, "status": "provisioning"}

    return {
        "custom_domain": rec["custom_domain"],
        "cname_target":  _PORTAL_HOST,
        "tenant_db":     tenant_db,
        "status":        rec["status"],
    }

@app.put("/api/v1/tenant/domain")
async def set_tenant_domain(req: DomainReq, auth: dict = Depends(require_auth)):
    """Set or update the tenant's custom domain. Validates format and uniqueness."""
    domain = req.domain.strip().lower().lstrip("https://").lstrip("http://").rstrip("/")

    if not domain:
        raise HTTPException(400, "Domain cannot be empty")
    if not _DOMAIN_RE.match(domain):
        raise HTTPException(400, "Invalid domain format — use e.g. erp.yourcompany.com")
    if len(domain) > 253:
        raise HTTPException(400, "Domain too long")
    # Block attempts to use our own hostname
    if domain == _PORTAL_HOST or domain.endswith("." + _PORTAL_HOST):
        raise HTTPException(400, "Cannot use mumtaz.digital domain — use your own domain")

    db  = get_db()
    row = db.execute(
        "SELECT tenant_db FROM users WHERE email = ?", (auth["email"],)
    ).fetchone()
    tenant_db = row["tenant_db"] if row else None
    if not tenant_db:
        db.close()
        raise HTTPException(400, "Your workspace is still being set up")

    # Check domain isn't already claimed by another tenant
    conflict = db.execute(
        "SELECT db_name FROM tenants WHERE custom_domain = ? AND db_name != ?",
        (domain, tenant_db),
    ).fetchone()
    if conflict:
        db.close()
        raise HTTPException(409, "This domain is already linked to another workspace")

    db.execute(
        "UPDATE tenants SET custom_domain = ? WHERE db_name = ?",
        (domain, tenant_db),
    )
    db.commit()
    db.close()

    return {
        "ok":           True,
        "custom_domain": domain,
        "cname_target":  _PORTAL_HOST,
        "message":       f"Point a CNAME record for {domain} → {_PORTAL_HOST}",
    }

@app.delete("/api/v1/tenant/domain")
async def remove_tenant_domain(auth: dict = Depends(require_auth)):
    """Remove the tenant's custom domain."""
    db  = get_db()
    row = db.execute(
        "SELECT tenant_db FROM users WHERE email = ?", (auth["email"],)
    ).fetchone()
    tenant_db = row["tenant_db"] if row else None
    if not tenant_db:
        db.close()
        raise HTTPException(400, "No workspace found")
    db.execute("UPDATE tenants SET custom_domain = NULL WHERE db_name = ?", (tenant_db,))
    db.commit()
    db.close()
    return {"ok": True}

# ── Plans / Billing ──────────────────────────────────────────────────
PLANS = {
    "trial": {
        "key": "trial", "name": "Trial", "price": 0, "currency": "AED",
        "interval": "14-day trial",
        "features": ["All ERP modules", "1 ZAKI agent", "Up to 3 users", "Email support"],
        "limits": {"users": 3, "agents": 1, "modules": -1},
        "apps": ["erp", "zaki"],
        "erp_modules": ["accounting", "inventory"],
    },
    "starter": {
        "key": "starter", "name": "Starter", "price": 199, "currency": "AED",
        "interval": "month",
        "features": ["Core ERP modules", "1 ZAKI agent", "Up to 5 users", "Email support"],
        "limits": {"users": 5, "agents": 1, "modules": 4},
        "apps": ["erp", "zaki"],
        "erp_modules": ["accounting", "inventory"],
    },
    "growth": {
        "key": "growth", "name": "Growth", "price": 499, "currency": "AED",
        "interval": "month",
        "features": ["All ERP modules", "3 ZAKI agents", "B2B marketplace", "Up to 25 users", "Priority email support"],
        "limits": {"users": 25, "agents": 3, "modules": -1},
        "apps": ["erp", "zaki", "marketplace"],
        "erp_modules": ["accounting", "inventory", "sales", "hr"],
    },
    "scale": {
        "key": "scale", "name": "Scale", "price": 1499, "currency": "AED",
        "interval": "month",
        "features": ["Everything in Growth", "All ZAKI agents", "Up to 100 users", "Phone + Slack support", "Dedicated account manager"],
        "limits": {"users": 100, "agents": -1, "modules": -1},
        "apps": ["erp", "zaki", "marketplace"],
        "erp_modules": ["accounting", "inventory", "sales", "hr", "manufacturing"],
    },
}

def _plan_apps(plan_key: str) -> set[str]:
    """App keys included in a package (defaults to trial's set)."""
    return set((PLANS.get(plan_key or "trial") or PLANS["trial"]).get("apps", []) or [])

def _plan_modules(plan_key: str) -> set[str]:
    """ERP module keys included in a package."""
    return set((PLANS.get(plan_key or "trial") or PLANS["trial"]).get("erp_modules", []) or [])

def _user_plan(email: str) -> str:
    db  = get_db()
    row = db.execute("SELECT plan FROM users WHERE email=?", (email,)).fetchone()
    db.close()
    return (row["plan"] if row and row["plan"] else "trial")

@app.get("/api/v1/plans")
async def list_plans():
    """Public — returns the plan catalog."""
    return {"plans": list(PLANS.values())}

@app.get("/api/v1/plan")
async def get_current_plan(auth: dict = Depends(require_auth)):
    db  = get_db()
    row = db.execute("SELECT plan FROM users WHERE email=?", (auth["email"],)).fetchone()
    db.close()
    current = (row["plan"] if row else "trial") or "trial"
    return {"current": current, "plan": PLANS.get(current, PLANS["trial"])}

class ChangePlanReq(BaseModel):
    plan: str

@app.post("/api/v1/plan")
async def change_plan(req: ChangePlanReq, background_tasks: BackgroundTasks,
                      auth: dict = Depends(require_auth)):
    """Change the user's plan and raise an Odoo SaaS invoice in the background."""
    if req.plan not in PLANS:
        raise HTTPException(400, f"Unknown plan '{req.plan}'. Valid: {list(PLANS.keys())}")
    db = get_db()
    row = db.execute("SELECT name FROM users WHERE email=?", (auth["email"],)).fetchone()
    user_name = row["name"] if row else None
    db.execute("UPDATE users SET plan=? WHERE email=?", (req.plan, auth["email"]))
    db.commit()
    db.close()
    background_tasks.add_task(_odoo_create_saas_invoice, auth["email"], user_name, req.plan)
    return {"ok": True, "plan": PLANS[req.plan]}

# ── ZATCA / e-invoicing ──────────────────────────────────────────────
@app.get("/api/v1/zatca/status")
def zatca_status(auth: dict = Depends(require_auth)):
    """Return the current ZATCA configuration state for the UI."""
    return zatca_svc.status()

class ZatcaQRReq(BaseModel):
    seller_name: str | None = None
    vat_number:  str | None = None
    timestamp:   str | None = None  # ISO 8601 UTC
    total_with_vat: str
    vat_amount:  str

@app.post("/api/v1/zatca/qr")
def zatca_generate_qr(req: ZatcaQRReq, auth: dict = Depends(require_auth)):
    """Generate a ZATCA-compliant base64 QR string for a simplified invoice.
    Falls back to env defaults when seller_name/vat_number aren't supplied."""
    from datetime import datetime, timezone
    if not zatca_svc.is_configured() and not (req.seller_name and req.vat_number):
        raise HTTPException(400, "ZATCA not configured. Provide seller_name + vat_number, "
                                  "or set ZATCA_SELLER_NAME + ZATCA_VAT_NUMBER on the server.")
    seller = req.seller_name or os.environ.get("ZATCA_SELLER_NAME", "")
    vat    = req.vat_number  or os.environ.get("ZATCA_VAT_NUMBER", "")
    ts     = req.timestamp   or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        qr = zatca_svc.build_qr(
            seller_name=seller, vat_number=vat, timestamp=ts,
            total_with_vat=req.total_with_vat, vat_amount=req.vat_amount,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"qr": qr, "timestamp": ts, "seller_name": seller, "vat_number": vat}

class ZatcaOnboardReq(BaseModel):
    otp: str
    csr_base64: str | None = None

@app.post("/api/v1/zatca/onboard")
def zatca_onboard(req: ZatcaOnboardReq, auth: dict = Depends(require_admin)):
    """Admin-only: submit CSR + OTP to ZATCA, persist returned CSID + secret.

    If csr_base64 is omitted, the caller must already have run
    /admin/settings/zatca/csr to generate one — we'll regenerate from the
    saved private key in that case (TODO: store the CSR alongside the key)."""
    if not req.csr_base64:
        raise HTTPException(400, "Provide csr_base64 from /admin/settings/zatca/csr.")
    try:
        result = zatca_svc.submit_csr_for_csid(
            csr_base64=req.csr_base64.strip(),
            otp=req.otp.strip(),
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))

    # Persist the returned token + secret so subsequent invoice submissions can authenticate.
    if result.get("binarySecurityToken"):
        settings.set_value("ZATCA_CSID", result["binarySecurityToken"], updated_by=auth.get("email"))
    return {
        "ok": True,
        "raw": result,
        "stored": {"ZATCA_CSID": bool(result.get("binarySecurityToken"))},
    }

class ZatcaSubmitReq(BaseModel):
    invoice_xml: str
    kind: str = "standard"  # standard | simplified

@app.post("/api/v1/zatca/submit")
def zatca_submit(req: ZatcaSubmitReq, auth: dict = Depends(require_auth)):
    """Submit a UBL 2.1 invoice for clearance (B2B) or reporting (B2C).
    Currently a stub — wire up real ZATCA API once credentials are loaded."""
    try:
        result = zatca_svc.submit_invoice(invoice_xml=req.invoice_xml, kind=req.kind)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))
    return result


# ── Admin: runtime settings ──────────────────────────────────────────
@app.get("/api/v1/admin/settings")
def admin_get_settings(auth: dict = Depends(require_admin)):
    """Return all manageable settings with their current value + source.
    Sensitive fields are masked. Admins can override via POST below."""
    return {
        "settings":      settings.list_all(masked=True),
        "allowed_keys":  list(settings.ALLOWED_KEYS),
        "sensitive_keys": list(settings.SENSITIVE_KEYS),
    }

class SettingsUpdateReq(BaseModel):
    values: dict   # {KEY: "value"}; empty string clears the override

@app.post("/api/v1/admin/settings")
def admin_update_settings(req: SettingsUpdateReq, auth: dict = Depends(require_admin)):
    """Bulk-update settings. Empty strings remove DB overrides (env wins again)."""
    accepted = settings.set_many(req.values, updated_by=auth.get("email"))
    rejected = sorted(set(req.values.keys()) - set(accepted))
    # Refresh module-level globals that some code reads at import time.
    global ADMIN_EMAILS, PORTAL_BASE_URL
    ADMIN_EMAILS    = admin_emails()
    PORTAL_BASE_URL = portal_base_url()
    return {"ok": True, "accepted": accepted, "rejected": rejected,
            "settings": settings.list_all(masked=True)}


class SmtpTestReq(BaseModel):
    to: str

@app.post("/api/v1/admin/settings/test/smtp")
def admin_test_smtp(req: SmtpTestReq, auth: dict = Depends(require_admin)):
    """Send a test email using whatever SMTP config is currently active."""
    if not (mailer._config().get("host") or "").strip():
        raise HTTPException(400, "SMTP_HOST is not configured.")
    ok = mailer.send_email(
        req.to.strip(),
        "Mumtaz SMTP test",
        "<p>This is a test message from your Mumtaz admin panel. "
        "If you can read it, SMTP is working.</p>",
        "Mumtaz SMTP test — if you can read this, SMTP is working.",
    )
    if not ok:
        raise HTTPException(502, "SMTP send failed. Check zaki-server logs.")
    return {"ok": True}


@app.post("/api/v1/admin/settings/test/stripe")
def admin_test_stripe(auth: dict = Depends(require_admin)):
    """Verify the configured Stripe secret key by making a tiny API call."""
    if not billing_svc.is_configured():
        raise HTTPException(400, "Stripe is not configured.")
    try:
        billing_svc._init()
        import stripe as _stripe  # noqa
        # Cheapest GET on the Stripe API: list a single price
        _stripe.Price.list(limit=1)
    except Exception as e:
        raise HTTPException(502, f"Stripe key rejected: {e}")
    return {"ok": True}


@app.get("/api/v1/admin/odoo/status")
def admin_odoo_status(auth: dict = Depends(require_admin)):
    """Detailed Odoo connectivity diagnostics. Exposes which DB / user / version
    is connected, how many internal users exist, and the last connectivity
    error (if any) — surfaced in the admin UI to diagnose connection issues
    without SSHing into the box."""
    info       = odoo_server_info()
    admin_uid  = odoo_get_admin_uid() if info else None
    user_count = None
    db_list    = None
    if admin_uid:
        try:
            uids = _odoo_object().execute_kw(
                ODOO_DB, admin_uid, ODOO_PASS, "res.users", "search",
                [[["share", "=", False]]],
            )
            user_count = len(uids)
        except Exception as e:
            _record_odoo_error("user_count", e)
        try:
            db_list = _odoo_common().db.list()
        except Exception:
            # `db.list` is often disabled by `list_db = False` in odoo.conf — non-fatal
            pass
    return {
        "url":           ODOO_URL,
        "db":            ODOO_DB,
        "admin_user":    ODOO_ADMIN,
        "timeout_secs":  ODOO_TIMEOUT,
        "connected":     bool(admin_uid),
        "admin_uid":     admin_uid,
        "server_info":   info,
        "internal_users": user_count,
        "available_dbs": db_list,
        "last_error":    _odoo_last_error,
    }


class OdooSearchReq(BaseModel):
    model: str
    domain: list = []
    fields: list[str] = []
    limit: int = 50

@app.post("/api/v1/admin/odoo/search")
def admin_odoo_search(req: OdooSearchReq, auth: dict = Depends(require_admin)):
    """Run an arbitrary search_read against any Odoo model. Admin-only,
    used by the admin UI for quick lookups (e.g. mumtaz.tenant, res.partner)."""
    admin_uid = odoo_get_admin_uid()
    if not admin_uid:
        raise HTTPException(503, "Odoo unreachable.")
    try:
        rows = _odoo_object().execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, req.model, "search_read",
            [req.domain],
            {"fields": req.fields or [], "limit": max(1, min(req.limit, 500))},
        )
    except Exception as e:
        _record_odoo_error(f"search_read({req.model})", e)
        raise HTTPException(400, f"Odoo error: {e}")
    return {"model": req.model, "count": len(rows), "rows": rows}


@app.post("/api/v1/admin/settings/zatca/csr")
def admin_zatca_csr(auth: dict = Depends(require_admin)):
    """Generate a fresh ZATCA EC keypair + CSR. The private key is saved
    automatically into ZATCA_PRIVATE_KEY; the CSR is returned for OTP submission."""
    vat    = (settings.get("ZATCA_VAT_NUMBER") or "").strip()
    seller = (settings.get("ZATCA_SELLER_NAME") or "").strip()
    if not vat or not seller:
        raise HTTPException(400, "Set ZATCA_VAT_NUMBER and ZATCA_SELLER_NAME first.")
    import secrets as _sec
    serial = "1-mumtaz|2-zaki|3-" + _sec.token_hex(8)
    pair = zatca_svc.generate_keypair_and_csr(
        common_name=seller, vat_number=vat,
        serial_number=serial, organization=seller,
    )
    settings.set_value("ZATCA_PRIVATE_KEY", pair["private_key_pem"], updated_by=auth.get("email"))
    return {
        "ok": True,
        "csr_pem":    pair["csr_pem"],
        "csr_base64": pair["csr_base64"],
        "next_step":  "Submit the CSR + your OTP to /api/v1/zatca/onboard.",
    }


# ── Partner / White-label ────────────────────────────────────────────
class PartnerSignupReq(BaseModel):
    company: str
    contact_name: str
    email: str
    phone: str | None = None
    country: str | None = None
    kind: str | None = None     # bank, freezone, chamber, agency, enterprise, other
    clients: str | None = None  # 1-50, 51-500, 500+
    domain: str | None = None   # e.g. "erp.mybank.ae"
    notes: str | None = None

@app.post("/api/v1/partner/signup")
def partner_signup(req: PartnerSignupReq, background_tasks: BackgroundTasks = None):
    """Receive a white-label partner application. Public — no auth required."""
    if not req.email.strip() or "@" not in req.email:
        raise HTTPException(400, "Valid email required.")
    if not req.company.strip():
        raise HTTPException(400, "Company name required.")
    if not req.contact_name.strip():
        raise HTTPException(400, "Contact name required.")

    db = get_db()
    db.execute(
        """INSERT INTO partners
           (company, contact_name, email, phone, country, kind, clients, domain, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req.company.strip(), req.contact_name.strip(), req.email.strip().lower(),
         req.phone, req.country, req.kind, req.clients, req.domain, req.notes),
    )
    db.commit(); db.close()

    # Notify admins (best-effort)
    if background_tasks is not None and ADMIN_EMAILS:
        subject = f"[Mumtaz] New partner application: {req.company}"
        html = (
            f"<h2>New partner application</h2>"
            f"<p><strong>{req.company}</strong> ({req.kind or 'unspecified'}) — "
            f"{req.clients or 'unknown'} clients · {req.country or 'unknown country'}</p>"
            f"<p>Contact: {req.contact_name} &lt;{req.email}&gt; · {req.phone or 'no phone'}</p>"
            f"<p>Desired domain: <code>{req.domain or 'not specified'}</code></p>"
            f"<p>Notes:<br><em>{(req.notes or '').replace(chr(10), '<br>')}</em></p>"
        )
        for admin in ADMIN_EMAILS:
            background_tasks.add_task(mailer.send_email, admin, subject, html)

    return {"ok": True, "message": "Application received. Our team will be in touch within 2 business days."}


@app.get("/api/v1/admin/partners")
def admin_list_partners(auth: dict = Depends(require_admin)):
    db = get_db()
    rows = db.execute("""
        SELECT id, company, contact_name, email, phone, country, kind, clients,
               domain, notes, status, created_at
        FROM partners
        ORDER BY created_at DESC
    """).fetchall()
    db.close()
    return {"partners": [dict(r) for r in rows]}


class PartnerStatusReq(BaseModel):
    status: str  # pending | approved | rejected

@app.post("/api/v1/admin/partners/{partner_id}/status")
def admin_partner_status(partner_id: int, req: PartnerStatusReq,
                         auth: dict = Depends(require_admin)):
    if req.status not in ("pending", "approved", "rejected"):
        raise HTTPException(400, "Invalid status.")
    db = get_db()
    if not db.execute("SELECT id FROM partners WHERE id=?", (partner_id,)).fetchone():
        db.close(); raise HTTPException(404, "Partner not found.")
    db.execute("UPDATE partners SET status=? WHERE id=?", (req.status, partner_id))
    db.commit(); db.close()
    return {"ok": True, "status": req.status}


# ── Stripe billing ───────────────────────────────────────────────────
class CheckoutReq(BaseModel):
    plan: str

@app.get("/api/v1/billing/status")
def billing_status():
    """Public — tells the front-end whether real Stripe Checkout is configured."""
    return {"stripe_configured": billing_svc.is_configured()}

@app.post("/api/v1/billing/checkout")
def billing_checkout(req: CheckoutReq, auth: dict = Depends(require_auth)):
    """Create a Stripe Checkout session for the given plan and return its URL."""
    if not billing_svc.is_configured():
        raise HTTPException(503, "Stripe is not configured. Plan changes happen directly via /api/v1/plan.")
    if req.plan not in PLANS or req.plan == "trial":
        raise HTTPException(400, "Invalid plan for checkout.")

    db  = get_db()
    row = db.execute("SELECT name FROM users WHERE email=?", (auth["email"],)).fetchone()
    db.close()
    name = row["name"] if row else None

    success_url = f"{PORTAL_BASE_URL}/billing.html?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{PORTAL_BASE_URL}/billing.html?checkout=cancelled"

    try:
        url = billing_svc.create_checkout_session(
            email=auth["email"], name=name, plan_key=req.plan,
            success_url=success_url, cancel_url=cancel_url,
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return {"url": url}

@app.post("/api/v1/billing/portal")
def billing_portal(auth: dict = Depends(require_auth)):
    """Open the Stripe Customer Portal for the signed-in user."""
    if not billing_svc.is_configured():
        raise HTTPException(503, "Stripe is not configured.")
    try:
        url = billing_svc.create_portal_session(
            email=auth["email"],
            return_url=f"{PORTAL_BASE_URL}/billing.html",
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return {"url": url}

@app.post("/api/v1/billing/webhook")
async def billing_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Stripe webhook events. Updates the user's plan in SQLite when
    a subscription is created, updated, or deleted, and raises an Odoo invoice.

    Idempotent: each Stripe event ID is recorded on first processing;
    duplicates are acknowledged without re-applying the plan change."""
    payload   = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = billing_svc.parse_webhook(payload, signature)
    except Exception as e:
        raise HTTPException(400, f"Invalid webhook: {e}")

    event_id = event.get("id") or ""
    if event_id:
        db = get_db()
        already = db.execute(
            "SELECT 1 FROM stripe_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if already:
            db.close()
            return {"received": True, "duplicate": True}
        db.execute("INSERT OR IGNORE INTO stripe_events (event_id) VALUES (?)", (event_id,))
        db.commit(); db.close()

    etype = event.get("type", "")
    obj   = (event.get("data") or {}).get("object") or {}

    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        plan_key = billing_svc.plan_from_event(obj)
        email    = billing_svc.email_from_event(obj)
        if plan_key and email:
            db = get_db()
            row = db.execute("SELECT name FROM users WHERE email=?", (email.lower(),)).fetchone()
            user_name = row["name"] if row else None
            db.execute("UPDATE users SET plan=? WHERE email=?", (plan_key, email.lower()))
            db.commit(); db.close()
            logger.info("[billing] subscription %s → %s = %s", etype, email, plan_key)
            background_tasks.add_task(_odoo_create_saas_invoice, email.lower(), user_name, plan_key)
    elif etype == "customer.subscription.deleted":
        email = billing_svc.email_from_event(obj)
        if email:
            db = get_db()
            db.execute("UPDATE users SET plan='trial' WHERE email=?", (email.lower(),))
            db.commit(); db.close()
            logger.info("[billing] subscription cancelled → %s dropped to trial", email)

    return {"received": True}

# ── Admin ────────────────────────────────────────────────────────────
@app.get("/api/v1/admin/ping")
def admin_ping(auth: dict = Depends(require_admin)):
    """Lightweight check used by /admin.html to confirm admin access."""
    return {"ok": True, "email": auth.get("email"), "admin_count": len(ADMIN_EMAILS)}

@app.get("/api/v1/admin/users")
def admin_list_users(auth: dict = Depends(require_admin)):
    db   = get_db()
    rows = db.execute("""
        SELECT id, email, name, company, plan, active, odoo_uid, tenant_id,
               created_at, onboarding_json, role, erp_company_id
        FROM users
        ORDER BY created_at DESC
    """).fetchall()
    db.close()
    import json as _json
    users = []
    for r in rows:
        try:
            ob = _json.loads(r["onboarding_json"]) if r["onboarding_json"] else None
        except Exception:
            ob = None
        users.append({
            "id":             r["id"],
            "email":          r["email"],
            "name":           r["name"],
            "company":        r["company"],
            "plan":           r["plan"] or "trial",
            "active":         bool(r["active"]),
            "odoo_uid":       r["odoo_uid"],
            "tenant_id":      r["tenant_id"],
            "erp_company_id": r["erp_company_id"],
            "created_at":     r["created_at"],
            "role":           r["role"],
            "products":       (ob or {}).get("products", []),
            "industry":       (ob or {}).get("industry"),
            "team_size":      (ob or {}).get("teamSize"),
            "is_admin":       (r["email"] or "").lower() in admin_emails(),
            "is_owner":       (r["email"] or "").lower() in owner_emails(),
        })
    return {"users": users, "total": len(users)}


# ── Owner: platform-wide oversight (tenants, revenue, apps) ──────────
def _validate_tenant_db(db_name: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT 1 FROM tenants WHERE db_name=?", (db_name,)).fetchone()
    conn.close()
    return bool(row)


@app.get("/api/v1/admin/overview")
def admin_overview(auth: dict = Depends(require_admin)):
    """Platform KPIs for the owner console: subscription MRR/ARR, tenant and
    user counts, and plan distribution. Local DB only — fast."""
    db = get_db()
    total_users    = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_users   = db.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
    total_tenants  = db.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
    active_tenants = db.execute("SELECT COUNT(*) FROM tenants WHERE status='active'").fetchone()[0]
    plan_rows = db.execute(
        "SELECT COALESCE(plan,'trial') p, COUNT(*) c FROM tenants GROUP BY p"
    ).fetchall()
    db.close()

    plans, mrr = {}, 0.0
    for r in plan_rows:
        key, cnt = r["p"], r["c"]
        price = float(PLANS.get(key, {}).get("price", 0) or 0)
        plans[key] = {"count": cnt, "price": price}
        mrr += price * cnt

    return {
        "currency": "AED",
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "users":   {"total": total_users,  "active": active_users},
        "tenants": {"total": total_tenants, "active": active_tenants},
        "plans": plans,
    }


@app.get("/api/v1/admin/tenants")
def admin_tenants(auth: dict = Depends(require_admin)):
    """List every tenant with plan, status, user count and subscription MRR.
    Their own business revenue is fetched per-row via .../revenue (owner)."""
    db = get_db()
    rows = db.execute("""
        SELECT id, db_name, company, admin_email, plan, status,
               custom_domain, created_at, provisioned_at, error_msg
        FROM tenants ORDER BY created_at DESC
    """).fetchall()
    counts = {r["tenant_db"]: r["c"] for r in db.execute(
        "SELECT tenant_db, COUNT(*) c FROM users WHERE tenant_db IS NOT NULL GROUP BY tenant_db"
    ).fetchall()}
    db.close()

    tenants = [{
        "id":             r["id"],
        "db_name":        r["db_name"],
        "company":        r["company"],
        "admin_email":    r["admin_email"],
        "plan":           r["plan"] or "trial",
        "status":         r["status"],
        "custom_domain":  r["custom_domain"],
        "created_at":     r["created_at"],
        "provisioned_at": r["provisioned_at"],
        "error_msg":      r["error_msg"],
        "users":          counts.get(r["db_name"], 0),
        "mrr":            float(PLANS.get(r["plan"] or "trial", {}).get("price", 0) or 0),
    } for r in rows]
    return {"tenants": tenants, "total": len(tenants), "currency": "AED"}


@app.get("/api/v1/admin/tenants/{db_name}/revenue")
def admin_tenant_revenue(db_name: str, auth: dict = Depends(require_owner)):
    """A single tenant's OWN business revenue from their Odoo accounting:
    posted customer-invoice total, invoice count, and customer count.
    Loaded per-row by the owner dashboard so the list stays fast."""
    if not _validate_tenant_db(db_name):
        raise HTTPException(404, "Unknown tenant")
    try:
        uid = odoo_get_admin_uid(db=db_name)
        if not uid:
            return {"db_name": db_name, "reachable": False}
        obj = _odoo_object()
        grp = obj.execute_kw(
            db_name, uid, ODOO_PASS, "account.move", "read_group",
            [[["move_type", "=", "out_invoice"], ["state", "=", "posted"]]],
            ["amount_total:sum"], [],
        )
        revenue  = (grp[0].get("amount_total") if grp else 0) or 0
        invoices = (grp[0].get("__count") if grp else 0) or 0
        try:
            customers = obj.execute_kw(db_name, uid, ODOO_PASS, "res.partner",
                                       "search_count", [[["customer_rank", ">", 0]]])
        except Exception:
            customers = 0
        currency = "AED"
        try:
            comp = obj.execute_kw(db_name, uid, ODOO_PASS, "res.company", "search_read",
                                  [[]], {"fields": ["currency_id"], "limit": 1})
            if comp and comp[0].get("currency_id"):
                currency = comp[0]["currency_id"][1]
        except Exception:
            pass
    except Exception as e:
        _record_odoo_error("admin_tenant_revenue", e)
        return {"db_name": db_name, "reachable": False}

    return {"db_name": db_name, "reachable": True, "revenue": round(revenue, 2),
            "invoices": invoices, "customers": customers, "currency": currency}


@app.get("/api/v1/admin/tenants/{db_name}/features")
def admin_get_tenant_features(db_name: str, auth: dict = Depends(require_owner)):
    """Read a specific tenant's app enable/disable state (owner oversight)."""
    if not _validate_tenant_db(db_name):
        raise HTTPException(404, "Unknown tenant")
    code_to_fid, modes = {}, {}
    try:
        uid = odoo_get_admin_uid(db=db_name)
        if not uid:
            raise RuntimeError("no admin uid")
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, db_name, uid, create=False)
        if tenant_id:
            codes = [s["code"] for s in APP_FEATURES.values()]
            feats = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.feature", "search_read",
                                   [[["code", "in", codes]]], {"fields": ["code"]})
            code_to_fid = {r["code"]: r["id"] for r in feats}
            fids = list(code_to_fid.values())
            if fids:
                ov = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature",
                                    "search_read",
                                    [[["tenant_id", "=", tenant_id], ["feature_id", "in", fids]]],
                                    {"fields": ["feature_id", "override_mode"]})
                modes = {r["feature_id"][0]: r["override_mode"] for r in ov}
    except Exception as e:
        _record_odoo_error("admin_get_tenant_features", e)
        raise HTTPException(502, "Could not read tenant apps")

    apps = []
    for k, s in APP_FEATURES.items():
        fid = code_to_fid.get(s["code"])
        mode = modes.get(fid) if fid else None
        apps.append({"key": k, "code": s["code"], "name": s["name"], "enabled": mode != "force_off"})
    return {"db_name": db_name, "apps": apps}


@app.put("/api/v1/admin/tenants/{db_name}/features")
def admin_set_tenant_feature(db_name: str, req: FeatureToggleReq,
                             auth: dict = Depends(require_owner)):
    """Enable/disable an app for a specific tenant (owner oversight)."""
    if not _validate_tenant_db(db_name):
        raise HTTPException(404, "Unknown tenant")
    spec = next((s for s in APP_FEATURES.values() if s["code"] == req.code), None)
    if not spec:
        raise HTTPException(400, "Unknown feature")
    try:
        uid = odoo_get_admin_uid(db=db_name)
        if not uid:
            raise RuntimeError("no admin uid")
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, db_name, uid, create=True)
        fid       = _erp_find_feature(obj, db_name, uid, spec, create=True)
        mode      = "force_on" if req.enabled else "force_off"
        existing  = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "search",
                                   [[["tenant_id", "=", tenant_id], ["feature_id", "=", fid]]],
                                   {"limit": 1})
        vals = {"override_mode": mode, "reason": f"Set by platform owner {auth.get('email')}."}
        if existing:
            obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "write", [existing, vals])
        else:
            obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "create",
                           [{**vals, "tenant_id": tenant_id, "feature_id": fid}])
        _enforce_marketplace_access(obj, db_name, uid, req.code, req.enabled)
    except HTTPException:
        raise
    except Exception as e:
        _record_odoo_error("admin_set_tenant_feature", e)
        raise HTTPException(502, "Could not update the tenant's app")
    return {"ok": True, "db_name": db_name, "code": req.code, "enabled": req.enabled}


class PlanChangeReq(BaseModel):
    plan: str

@app.put("/api/v1/admin/tenants/{db_name}/plan")
def admin_set_tenant_plan(db_name: str, req: PlanChangeReq,
                          auth: dict = Depends(require_owner)):
    """
    Assign a package to a tenant. The package is the single lever: it sets the
    billing plan AND re-applies the apps it includes (force_on included,
    force_off excluded) in the tenant's Odoo control plane, with marketplace
    group enforcement. Billing + apps stay in lock-step.
    """
    if req.plan not in PLANS:
        raise HTTPException(400, f"Unknown plan '{req.plan}'")
    if not _validate_tenant_db(db_name):
        raise HTTPException(404, "Unknown tenant")

    # 1. Billing: persist the plan on the tenant registry + its users.
    conn = get_db()
    conn.execute("UPDATE tenants SET plan=? WHERE db_name=?", (req.plan, db_name))
    conn.execute("UPDATE users SET plan=? WHERE tenant_db=?", (req.plan, db_name))
    conn.commit()
    conn.close()

    # 2. Apps: align overrides with the package's included apps.
    included = _plan_apps(req.plan)
    synced = {}
    try:
        uid = odoo_get_admin_uid(db=db_name)
        if uid:
            obj = _odoo_object()
            tenant_id = _erp_find_tenant(obj, db_name, uid, create=True)
            for key, spec in APP_FEATURES.items():
                enabled = key in included
                fid  = _erp_find_feature(obj, db_name, uid, spec, create=True)
                mode = "force_on" if enabled else "force_off"
                existing = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature",
                                          "search",
                                          [[["tenant_id", "=", tenant_id], ["feature_id", "=", fid]]],
                                          {"limit": 1})
                vals = {"override_mode": mode,
                        "reason": f"Package '{req.plan}' applied by owner {auth.get('email')}."}
                if existing:
                    obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "write",
                                   [existing, vals])
                else:
                    obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "create",
                                   [{**vals, "tenant_id": tenant_id, "feature_id": fid}])
                _enforce_marketplace_access(obj, db_name, uid, spec["code"], enabled)
                synced[key] = enabled

            # Align ERP sub-modules with the package too.
            mods_incl = _plan_modules(req.plan)
            for mkey, mspec in ERP_MODULES.items():
                men  = mkey in mods_incl
                mfid = _erp_find_feature(obj, db_name, uid, mspec, create=True)
                mmode = "force_on" if men else "force_off"
                mex = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "search",
                                     [[["tenant_id", "=", tenant_id], ["feature_id", "=", mfid]]], {"limit": 1})
                mvals = {"override_mode": mmode,
                         "reason": f"Package '{req.plan}' applied by owner {auth.get('email')}."}
                if mex:
                    obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "write", [mex, mvals])
                else:
                    obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "create",
                                   [{**mvals, "tenant_id": tenant_id, "feature_id": mfid}])
                _enforce_module_access(obj, db_name, uid, mkey, men)
                synced["module:" + mkey] = men
    except Exception as e:
        # Plan is already saved in the registry; app sync is best-effort.
        _record_odoo_error("admin_set_tenant_plan", e)

    return {"ok": True, "db_name": db_name, "plan": req.plan, "apps": synced}


@app.get("/api/v1/admin/tenants/{db_name}/modules")
def admin_get_tenant_modules(db_name: str, auth: dict = Depends(require_owner)):
    """Read a tenant's ERP module enable/disable state (owner oversight)."""
    if not _validate_tenant_db(db_name):
        raise HTTPException(404, "Unknown tenant")
    c2f, modes = {}, {}
    try:
        uid = odoo_get_admin_uid(db=db_name)
        if not uid:
            raise RuntimeError("no admin uid")
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, db_name, uid, create=False)
        if tenant_id:
            codes = [s["code"] for s in ERP_MODULES.values()]
            feats = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.feature", "search_read",
                                   [[["code", "in", codes]]], {"fields": ["code"]})
            c2f = {r["code"]: r["id"] for r in feats}
            fids = list(c2f.values())
            if fids:
                ov = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "search_read",
                                    [[["tenant_id", "=", tenant_id], ["feature_id", "in", fids]]],
                                    {"fields": ["feature_id", "override_mode"]})
                modes = {r["feature_id"][0]: r["override_mode"] for r in ov}
    except Exception as e:
        _record_odoo_error("admin_get_tenant_modules", e)
        raise HTTPException(502, "Could not read tenant modules")
    mods = []
    for k, s in ERP_MODULES.items():
        fid = c2f.get(s["code"])
        mode = modes.get(fid) if fid else None
        mods.append({"key": k, "code": s["code"], "name": s["name"], "enabled": mode != "force_off"})
    return {"db_name": db_name, "modules": mods}


@app.put("/api/v1/admin/tenants/{db_name}/modules")
def admin_set_tenant_module(db_name: str, req: ModuleToggleReq,
                            auth: dict = Depends(require_owner)):
    """Enable/disable an ERP module for a specific tenant (owner oversight)."""
    spec = ERP_MODULES.get(req.key)
    if not spec:
        raise HTTPException(400, "Unknown module")
    if not _validate_tenant_db(db_name):
        raise HTTPException(404, "Unknown tenant")
    try:
        uid = odoo_get_admin_uid(db=db_name)
        if not uid:
            raise RuntimeError("no admin uid")
        obj = _odoo_object()
        tenant_id = _erp_find_tenant(obj, db_name, uid, create=True)
        fid       = _erp_find_feature(obj, db_name, uid, spec, create=True)
        mode      = "force_on" if req.enabled else "force_off"
        existing  = obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "search",
                                   [[["tenant_id", "=", tenant_id], ["feature_id", "=", fid]]], {"limit": 1})
        vals = {"override_mode": mode, "reason": f"Module set by owner {auth.get('email')}."}
        if existing:
            obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "write", [existing, vals])
        else:
            obj.execute_kw(db_name, uid, ODOO_PASS, "mumtaz.tenant.feature", "create",
                           [{**vals, "tenant_id": tenant_id, "feature_id": fid}])
        _enforce_module_access(obj, db_name, uid, req.key, req.enabled)
    except HTTPException:
        raise
    except Exception as e:
        _record_odoo_error("admin_set_tenant_module", e)
        raise HTTPException(502, "Could not update the tenant's module")
    return {"ok": True, "db_name": db_name, "key": req.key, "enabled": req.enabled}


@app.post("/api/v1/admin/sync-erp")
def admin_sync_erp(auth: dict = Depends(require_admin)):
    """Provision all active portal users (who have a company) into the ERP as tenants."""
    import secrets as _secrets
    import urllib.request as _url
    import json as _json

    erp_url     = settings.get("ERP_API_URL",    "https://erp.mumtaz.digital")
    portal_key  = settings.get("PORTAL_API_KEY", "mumtaz-portal-key-change-me")

    db   = get_db()
    rows = db.execute(
        "SELECT id, email, name, company, erp_company_id FROM users WHERE active=1"
    ).fetchall()
    db.close()

    synced, skipped, failed = [], [], []

    for row in rows:
        if not row["company"]:
            continue
        if row["erp_company_id"]:
            skipped.append({"email": row["email"], "erp_company_id": row["erp_company_id"]})
            continue
        temp_pass = _secrets.token_urlsafe(10)
        payload   = _json.dumps({
            "portal_api_key": portal_key,
            "company_name":   row["company"],
            "admin_email":    row["email"],
            "admin_password": temp_pass,
        }).encode()
        try:
            req = _url.Request(
                f"{erp_url}/api/portal/provision",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _url.urlopen(req, timeout=20) as resp:
                data = _json.loads(resp.read())
            cid = data.get("company_id")
            db2 = get_db()
            db2.execute("UPDATE users SET erp_company_id=? WHERE id=?", (cid, row["id"]))
            db2.commit(); db2.close()
            synced.append({
                "email":        row["email"],
                "company":      row["company"],
                "erp_company_id": cid,
                "temp_password":  temp_pass if not data.get("already_existed") else "(existing account)",
            })
        except Exception as e:
            failed.append({"email": row["email"], "error": str(e)})

    return {
        "synced":  synced,
        "skipped": skipped,
        "failed":  failed,
        "summary": f"{len(synced)} synced, {len(skipped)} already synced, {len(failed)} failed",
    }

class AdminToggleReq(BaseModel):
    active: bool

@app.post("/api/v1/admin/users/{user_id}/toggle")
def admin_toggle_user(user_id: int, req: AdminToggleReq, auth: dict = Depends(require_admin)):
    db = get_db()
    row = db.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        db.close(); raise HTTPException(404, "User not found.")
    if (row["email"] or "").lower() in ADMIN_EMAILS:
        db.close(); raise HTTPException(400, "Cannot deactivate an admin.")
    db.execute("UPDATE users SET active=? WHERE id=?", (1 if req.active else 0, user_id))
    db.commit(); db.close()
    return {"ok": True, "active": req.active}

@app.post("/api/v1/admin/users/{user_id}/make-admin")
def admin_make_admin(user_id: int, auth: dict = Depends(require_admin)):
    """Promote a portal user to platform admin (adds to MUMTAZ_ADMINS)."""
    db = get_db()
    row = db.execute("SELECT email, name FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "User not found.")
    email = (row["email"] or "").lower()
    current = settings.get("MUMTAZ_ADMINS", "") or ""
    existing = {e.strip().lower() for e in current.split(",") if e.strip()}
    if email not in existing:
        existing.add(email)
        settings.set_value("MUMTAZ_ADMINS", ",".join(sorted(existing)), updated_by=auth.get("email"))
    global ADMIN_EMAILS
    ADMIN_EMAILS = admin_emails()
    return {"ok": True, "email": email, "is_admin": True}

class AdminPlanReq(BaseModel):
    plan: str

@app.post("/api/v1/admin/users/{user_id}/plan")
def admin_change_user_plan(user_id: int, req: AdminPlanReq,
                           background_tasks: BackgroundTasks,
                           auth: dict = Depends(require_admin)):
    if req.plan not in PLANS:
        raise HTTPException(400, f"Unknown plan '{req.plan}'.")
    db = get_db()
    row = db.execute("SELECT email, name FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        db.close(); raise HTTPException(404, "User not found.")
    email, name = row["email"], row["name"]
    db.execute("UPDATE users SET plan=? WHERE id=?", (req.plan, user_id))
    db.commit(); db.close()
    background_tasks.add_task(_odoo_create_saas_invoice, email, name, req.plan)
    return {"ok": True, "plan": PLANS[req.plan]}

@app.get("/api/v1/tenant/me")
async def tenant_me(auth: dict = Depends(require_auth)):
    tenant_id = auth.get("tenant_id")
    if not tenant_id:
        return {"tenant": None}
    return {"tenant": odoo_read_tenant(int(tenant_id))}

@app.get("/api/v1/modules")
async def get_modules(auth: dict = Depends(require_auth)):
    """Return installed state of each portal module from Odoo ERP."""
    return {"modules": odoo_get_module_states()}

class ModuleToggleReq(BaseModel):
    module_id: str

@app.post("/api/v1/modules/install")
async def install_module(req: ModuleToggleReq, auth: dict = Depends(require_auth)):
    if req.module_id not in MODULE_MAP:
        raise HTTPException(400, f"Unknown module: {req.module_id}")
    ok = odoo_toggle_module(req.module_id, install=True)
    if not ok:
        raise HTTPException(500, f"Failed to install {req.module_id}")
    return {"ok": True, "module": req.module_id, "installed": True}

@app.post("/api/v1/modules/uninstall")
async def uninstall_module(req: ModuleToggleReq, auth: dict = Depends(require_auth)):
    if req.module_id not in MODULE_MAP:
        raise HTTPException(400, f"Unknown module: {req.module_id}")
    ok = odoo_toggle_module(req.module_id, install=False)
    if not ok:
        raise HTTPException(500, f"Failed to uninstall {req.module_id}")
    return {"ok": True, "module": req.module_id, "installed": False}

@app.get("/api/v1/dashboard")
async def get_dashboard(auth: dict = Depends(require_auth)):
    """Real KPIs pulled from Odoo: invoices, revenue, outstanding, user count."""
    admin_uid = odoo_get_admin_uid()
    obj = _odoo_object()

    kpis = {
        "invoiced": 0.0, "invoice_count": 0,
        "outstanding": 0.0, "paid": 0.0,
        "currency": "AED",
    }
    users_data = {"active": 1, "total": 1}
    recent_invoices = []

    if admin_uid:
        try:
            rows = obj.execute_kw(
                ODOO_DB, admin_uid, ODOO_PASS, "account.move", "search_read",
                [[["move_type", "=", "out_invoice"], ["state", "=", "posted"]]],
                {"fields": ["name", "partner_id", "amount_total", "amount_residual",
                            "invoice_date", "payment_state", "currency_id"],
                 "order": "invoice_date desc", "limit": 100}
            )
            kpis["invoice_count"] = len(rows)
            kpis["invoiced"]      = round(sum(r["amount_total"] for r in rows), 2)
            kpis["outstanding"]   = round(sum(r["amount_residual"] for r in rows), 2)
            kpis["paid"]          = round(kpis["invoiced"] - kpis["outstanding"], 2)
            if rows and isinstance(rows[0].get("currency_id"), list):
                kpis["currency"] = rows[0]["currency_id"][1]
            recent_invoices = [
                {
                    "name":    r["name"],
                    "partner": r["partner_id"][1] if isinstance(r["partner_id"], list) else "",
                    "amount":  r["amount_total"],
                    "residual":r["amount_residual"],
                    "date":    r["invoice_date"],
                    "status":  r["payment_state"],
                    "currency":kpis["currency"],
                }
                for r in rows[:10]
            ]
        except Exception as e:
            logger.error("[dashboard] invoice fetch error: %s", e)

        try:
            uid_list = obj.execute_kw(
                ODOO_DB, admin_uid, ODOO_PASS, "res.users", "search",
                [[["active", "=", True], ["share", "=", False]]]
            )
            users_data["active"] = len(uid_list)
            users_data["total"]  = len(uid_list)
        except Exception as e:
            logger.error("[dashboard] users fetch error: %s", e)

    # Pull plan from SQLite
    plan = auth.get("plan", "trial")

    return {
        "kpis":            kpis,
        "users":           users_data,
        "recent_invoices": recent_invoices,
        "plan":            plan,
    }

@app.post("/api/v1/zaki/sync-odoo")
async def zaki_sync_odoo(auth: dict = Depends(require_auth)):
    """Pull the authenticated user's posted invoices and bills from Odoo and
    return them in Zaki's transaction format. Frontend writes them into
    S.transactions; computeFin() then derives KPIs."""
    admin_uid = odoo_get_admin_uid()
    if not admin_uid:
        raise HTTPException(503, "Odoo unreachable.")

    obj = _odoo_object()
    user_odoo_uid = auth.get("odoo_uid")
    company_id = None
    company_name = None
    currency = "AED"

    # Find the user's company. If not linked to Odoo (rare — local-only login),
    # fall back to admin's default company.
    try:
        target_uid = int(user_odoo_uid) if user_odoo_uid else admin_uid
        rows = obj.execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "res.users", "read",
            [[target_uid]],
            {"fields": ["company_id", "name"]},
        )
        if rows and isinstance(rows[0].get("company_id"), list):
            company_id = rows[0]["company_id"][0]
            company_name = rows[0]["company_id"][1]
    except Exception as e:
        _record_odoo_error("sync_odoo:user_company", e)
        raise HTTPException(502, f"Could not resolve Odoo company: {e}")

    if not company_id:
        raise HTTPException(404, "User has no Odoo company assigned.")

    # Last 12 months of posted invoices + bills for this company
    cutoff = (datetime.utcnow() - timedelta(days=365)).date().isoformat()
    domain_inv = [
        ["company_id", "=", company_id],
        ["move_type", "in", ["out_invoice", "out_refund"]],
        ["state", "=", "posted"],
        ["invoice_date", ">=", cutoff],
    ]
    domain_bill = [
        ["company_id", "=", company_id],
        ["move_type", "in", ["in_invoice", "in_refund"]],
        ["state", "=", "posted"],
        ["invoice_date", ">=", cutoff],
    ]
    fields = ["name", "invoice_date", "amount_total", "amount_residual",
              "currency_id", "partner_id", "payment_state", "ref", "move_type"]

    transactions: list[dict] = []
    ar_outstanding = 0.0
    ap_outstanding = 0.0

    try:
        invoices = obj.execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "account.move", "search_read",
            [domain_inv],
            {"fields": fields, "order": "invoice_date desc", "limit": 1000},
        )
        for r in invoices:
            sign = -1 if r["move_type"] == "out_refund" else 1
            amt = float(r.get("amount_total", 0)) * sign
            transactions.append({
                "id": f"odoo_inv_{r['id']}",
                "date": str(r.get("invoice_date") or "")[:10],
                "amount": abs(amt),
                "type": "income" if amt >= 0 else "expense",
                "category": "Sales" if amt >= 0 else "Sales Refund",
                "description": r.get("name") or "Invoice",
                "reference": (r["partner_id"][1] if isinstance(r.get("partner_id"), list) else "") or r.get("ref") or "",
                "source": "odoo",
            })
            ar_outstanding += float(r.get("amount_residual", 0))
            if isinstance(r.get("currency_id"), list):
                currency = r["currency_id"][1]
    except Exception as e:
        _record_odoo_error("sync_odoo:invoices", e)
        raise HTTPException(502, f"Invoice fetch failed: {e}")

    try:
        bills = obj.execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "account.move", "search_read",
            [domain_bill],
            {"fields": fields, "order": "invoice_date desc", "limit": 1000},
        )
        for r in bills:
            sign = -1 if r["move_type"] == "in_refund" else 1
            amt = float(r.get("amount_total", 0)) * sign
            transactions.append({
                "id": f"odoo_bill_{r['id']}",
                "date": str(r.get("invoice_date") or "")[:10],
                "amount": abs(amt),
                "type": "expense" if amt >= 0 else "income",
                "category": "Bill" if amt >= 0 else "Bill Refund",
                "description": r.get("name") or "Bill",
                "reference": (r["partner_id"][1] if isinstance(r.get("partner_id"), list) else "") or r.get("ref") or "",
                "source": "odoo",
            })
            ap_outstanding += float(r.get("amount_residual", 0))
    except Exception as e:
        _record_odoo_error("sync_odoo:bills", e)
        raise HTTPException(502, f"Bill fetch failed: {e}")

    return {
        "company": {"id": company_id, "name": company_name, "currency": currency},
        "transactions": transactions,
        "ar_outstanding": round(ar_outstanding, 2),
        "ap_outstanding": round(ap_outstanding, 2),
        "synced_count": len(transactions),
    }


@app.post("/api/v1/ai/chat/stream")
async def chat_stream(req: ChatReq, auth: dict = Depends(require_auth)):
    if not ANT_KEY:
        raise HTTPException(503, "AI not configured — set ANTHROPIC_API_KEY in /opt/zaki-server/.env")

    client = Anthropic(api_key=ANT_KEY)
    system = (
        "You are ZAKI, an AI CFO and financial advisor for Mumtaz Platform customers "
        "in the UAE/GCC region. Be concise, data-driven, and actionable."
    )
    if req.context:
        system += f"\n\nFinancial context:\n{req.context}"

    async def generate():
        try:
            with client.messages.stream(
                model=ZAKI_MODEL,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": req.message}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'text': f'[Error: {e}]'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
