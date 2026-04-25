"""
Mumtaz Auth & AI API
- Single auth backend for all Mumtaz products (portal, ERP, ZAKI CFO, marketplace)
- Validates credentials against Odoo via XML-RPC (single source of truth)
- Creates Odoo users + mumtaz.tenant records on signup
- Issues JWT used by all frontends
"""

import os, json, re, time, sqlite3
import xmlrpc.client
from datetime import datetime, timezone, timedelta

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
SECRET      = os.environ.get("JWT_SECRET",        "change-me-in-production")
ALGO        = "HS256"
TOKEN_DAYS  = 30
ANT_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
DB_PATH     = os.environ.get("DB_PATH",            "/opt/zaki-server/users.db")

ODOO_URL    = os.environ.get("ODOO_URL",            "http://127.0.0.1:8069")
ODOO_DB     = os.environ.get("ODOO_DB",             "mumtaz")
ODOO_ADMIN  = os.environ.get("ODOO_ADMIN_USER",     "admin")
ODOO_PASS   = os.environ.get("ODOO_ADMIN_PASS",     "admin")
ODOO_TIMEOUT = int(os.environ.get("ODOO_TIMEOUT",   "15"))

def _hash_pw(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def _verify_pw(password: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(title="Mumtaz Auth & AI API", version="2.0.0")

_cors_env = os.environ.get("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
        print("[init_db] old schema detected — rebuilding users table")
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
            print(f"[init_db] data migration error: {e}")
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
            ("role",      "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except Exception:
                pass

    conn.execute(_RESET_TOKENS_DDL)
    conn.execute(_PARTNERS_DDL)
    conn.commit()
    conn.close()

# ── JWT ───────────────────────────────────────────────────────────────
def make_token(user_id: int, email: str, extra: dict = None) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": int(time.time()) + 86400 * TOKEN_DAYS,
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
    print(f"[Odoo] {where} error: {exc}")

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

def odoo_get_admin_uid() -> int | None:
    try:
        uid = _odoo_common().authenticate(ODOO_DB, ODOO_ADMIN, ODOO_PASS, {})
        return uid if uid else None
    except Exception as e:
        _record_odoo_error("admin_auth", e)
        return None

def odoo_authenticate(email: str, password: str) -> int | None:
    """Returns Odoo UID on success, None on failure (wrong creds OR network down)."""
    try:
        uid = _odoo_common().authenticate(ODOO_DB, email, password, {})
        return uid if uid else None
    except Exception as e:
        _record_odoo_error("user_auth", e)
        return None

def odoo_create_user(name: str, email: str, password: str) -> int | None:
    """Create an internal Odoo user. Returns res.users ID."""
    admin_uid = odoo_get_admin_uid()
    if not admin_uid:
        print("[Odoo] cannot create user — admin auth failed")
        return None
    try:
        obj = _odoo_object()
        user_id = obj.execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "res.users", "create", [{
                "name": name,
                "login": email,
                "email": email,
                "password": password,
            }]
        )
        return user_id
    except Exception as e:
        _record_odoo_error("create_user", e)
        return None

def odoo_set_password(odoo_uid: int, new_password: str) -> bool:
    """Update an Odoo user's password. Used by the password-reset flow so
    users can actually log in after resetting (Odoo is the auth source of truth)."""
    admin_uid = odoo_get_admin_uid()
    if not admin_uid or not odoo_uid:
        return False
    try:
        _odoo_object().execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "res.users", "write",
            [[int(odoo_uid)], {"password": new_password}],
        )
        return True
    except Exception as e:
        _record_odoo_error("set_password", e)
        return False

def odoo_read_user(odoo_uid: int) -> dict:
    admin_uid = odoo_get_admin_uid()
    if not admin_uid or not odoo_uid:
        return {}
    try:
        rows = _odoo_object().execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "res.users", "read",
            [[odoo_uid]], {"fields": ["name", "email", "login"]}
        )
        return rows[0] if rows else {}
    except Exception as e:
        _record_odoo_error("read_user", e)
        return {}

def _make_tenant_code(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", company.lower())[:8] or "co"
    suffix = str(int(time.time()))[-5:]
    code = slug + suffix          # e.g. "acme12345" — satisfies [a-z0-9]{3-30}
    return code[:30]

def odoo_create_tenant(company: str, admin_email: str, admin_name: str) -> int | None:
    """Create a mumtaz.tenant draft record. Returns tenant ID."""
    admin_uid = odoo_get_admin_uid()
    if not admin_uid:
        return None
    try:
        obj    = _odoo_object()
        code   = _make_tenant_code(company)
        db_name = "mt_" + code                 # mt_acme12345

        # Find a default bundle (first available)
        bundles = obj.execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "mumtaz.module.bundle", "search",
            [[]], {"limit": 1}
        )
        bundle_id = bundles[0] if bundles else False

        tenant_id = obj.execute_kw(
            ODOO_DB, admin_uid, ODOO_PASS, "mumtaz.tenant", "create", [{
                "name": company,
                "code": code,
                "database_name": db_name,
                "admin_email": admin_email,
                "admin_name": admin_name,
                "bundle_id": bundle_id,
                "state": "draft",
            }]
        )
        return tenant_id
    except Exception as e:
        print(f"[Odoo] create tenant error: {e}")
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
        print(f"[modules] get states error: {e}")
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
        print(f"[modules] toggle error ({portal_id}, install={install}): {e}")
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
@app.on_event("startup")
def startup():
    init_db()
    settings.init_db()

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

@app.post("/api/v1/auth/signup")
def signup(req: SignupReq, background_tasks: BackgroundTasks = None):
    email = req.email.strip().lower()
    db    = get_db()

    if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        db.close()
        raise HTTPException(400, detail="An account with this email already exists.")

    # 1. Create Odoo user
    odoo_uid = odoo_create_user(req.name, email, req.password)

    # 2. Create mumtaz.tenant record in Odoo
    tenant_id = odoo_create_tenant(req.company, email, req.name)

    # 3. Cache in SQLite
    ph = _hash_pw(req.password)
    db.execute(
        "INSERT INTO users (email, password_hash, name, company, odoo_uid, tenant_id, plan) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, ph, req.name, req.company, odoo_uid, tenant_id, "trial")
    )
    db.commit()
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    # 4. Welcome email (background — never blocks signup)
    if background_tasks is not None:
        subject, html, text = mailer.welcome_email(req.name, email)
        background_tasks.add_task(mailer.send_email, email, subject, html, text)

    token = make_token(row["id"], email, {
        "name": req.name, "company": req.company,
        "odoo_uid": odoo_uid, "tenant_id": tenant_id, "plan": "trial",
    })
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "name":      req.name,
            "email":     email,
            "company":   req.company,
            "plan":      "trial",
            "odoo_uid":  odoo_uid,
            "tenant_id": tenant_id,
        },
    }

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

def admin_emails() -> set[str]:
    """Live read so admins added through the UI take effect immediately."""
    raw = settings.get("MUMTAZ_ADMINS", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}

# Backwards-compat shim — modules importing ADMIN_EMAILS still see the env list.
ADMIN_EMAILS = admin_emails()

def require_admin(auth: dict = Depends(require_auth)) -> dict:
    if (auth.get("email") or "").lower() not in admin_emails():
        raise HTTPException(403, "Admin access required.")
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
        # Primary: validate against Odoo
        odoo_uid = odoo_authenticate(email, req.password)

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
        print(f"[login] unexpected error: {e}")
        db.close()
        raise HTTPException(500, detail=f"Login error: {e}")

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
        },
    }

@app.get("/api/v1/auth/me")
async def me(auth: dict = Depends(require_auth)):
    db  = get_db()
    row = db.execute("SELECT * FROM users WHERE email=?", (auth["email"],)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, detail="User not found.")
    return {
        "name":      row["name"],
        "email":     row["email"],
        "company":   row["company"],
        "plan":      row["plan"],
        "odoo_uid":  row["odoo_uid"],
        "tenant_id": row["tenant_id"],
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

# ── Plans / Billing ──────────────────────────────────────────────────
PLANS = {
    "trial": {
        "key": "trial", "name": "Trial", "price": 0, "currency": "AED",
        "interval": "14-day trial",
        "features": ["All ERP modules", "1 ZAKI agent", "Up to 3 users", "Email support"],
        "limits": {"users": 3, "agents": 1, "modules": -1},
    },
    "starter": {
        "key": "starter", "name": "Starter", "price": 199, "currency": "AED",
        "interval": "month",
        "features": ["Core ERP modules", "1 ZAKI agent", "Up to 5 users", "Email support"],
        "limits": {"users": 5, "agents": 1, "modules": 4},
    },
    "growth": {
        "key": "growth", "name": "Growth", "price": 499, "currency": "AED",
        "interval": "month",
        "features": ["All ERP modules", "3 ZAKI agents", "B2B marketplace", "Up to 25 users", "Priority email support"],
        "limits": {"users": 25, "agents": 3, "modules": -1},
    },
    "scale": {
        "key": "scale", "name": "Scale", "price": 1499, "currency": "AED",
        "interval": "month",
        "features": ["Everything in Growth", "All ZAKI agents", "Up to 100 users", "Phone + Slack support", "Dedicated account manager"],
        "limits": {"users": 100, "agents": -1, "modules": -1},
    },
}

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
async def change_plan(req: ChangePlanReq, auth: dict = Depends(require_auth)):
    """Change the user's plan. No payment integration yet — this just
    updates the SQLite record so the rest of the platform reflects it.
    A real implementation would create a Stripe/Tap subscription here."""
    if req.plan not in PLANS:
        raise HTTPException(400, f"Unknown plan '{req.plan}'. Valid: {list(PLANS.keys())}")
    db = get_db()
    db.execute("UPDATE users SET plan=? WHERE email=?", (req.plan, auth["email"]))
    db.commit()
    db.close()
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
async def billing_webhook(request: Request):
    """Receive Stripe webhook events. Updates the user's plan in SQLite when
    a subscription is created, updated, or deleted."""
    payload   = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = billing_svc.parse_webhook(payload, signature)
    except Exception as e:
        raise HTTPException(400, f"Invalid webhook: {e}")

    etype = event.get("type", "")
    obj   = (event.get("data") or {}).get("object") or {}

    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        plan_key = billing_svc.plan_from_event(obj)
        email    = billing_svc.email_from_event(obj)
        if plan_key and email:
            db = get_db()
            db.execute("UPDATE users SET plan=? WHERE email=?", (plan_key, email.lower()))
            db.commit(); db.close()
            print(f"[billing] subscription {etype} → {email} = {plan_key}")
    elif etype == "customer.subscription.deleted":
        email = billing_svc.email_from_event(obj)
        if email:
            db = get_db()
            db.execute("UPDATE users SET plan='trial' WHERE email=?", (email.lower(),))
            db.commit(); db.close()
            print(f"[billing] subscription cancelled → {email} dropped to trial")

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
               created_at, onboarding_json, role
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
            "id":         r["id"],
            "email":      r["email"],
            "name":       r["name"],
            "company":    r["company"],
            "plan":       r["plan"] or "trial",
            "active":     bool(r["active"]),
            "odoo_uid":   r["odoo_uid"],
            "tenant_id":  r["tenant_id"],
            "created_at": r["created_at"],
            "role":       r["role"],
            "products":   (ob or {}).get("products", []),
            "industry":   (ob or {}).get("industry"),
            "team_size":  (ob or {}).get("teamSize"),
            "is_admin":   (r["email"] or "").lower() in ADMIN_EMAILS,
        })
    return {"users": users, "total": len(users)}

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

class AdminPlanReq(BaseModel):
    plan: str

@app.post("/api/v1/admin/users/{user_id}/plan")
def admin_change_user_plan(user_id: int, req: AdminPlanReq, auth: dict = Depends(require_admin)):
    if req.plan not in PLANS:
        raise HTTPException(400, f"Unknown plan '{req.plan}'.")
    db = get_db()
    if not db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone():
        db.close(); raise HTTPException(404, "User not found.")
    db.execute("UPDATE users SET plan=? WHERE id=?", (req.plan, user_id))
    db.commit(); db.close()
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
            print(f"[dashboard] invoice fetch error: {e}")

        try:
            uid_list = obj.execute_kw(
                ODOO_DB, admin_uid, ODOO_PASS, "res.users", "search",
                [[["active", "=", True], ["share", "=", False]]]
            )
            users_data["active"] = len(uid_list)
            users_data["total"]  = len(uid_list)
        except Exception as e:
            print(f"[dashboard] users fetch error: {e}")

    # Pull plan from SQLite
    plan = auth.get("plan", "trial")

    return {
        "kpis":            kpis,
        "users":           users_data,
        "recent_invoices": recent_invoices,
        "plan":            plan,
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
                model="claude-sonnet-4-5",
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
