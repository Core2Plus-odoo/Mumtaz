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

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from jose import jwt, JWTError
import bcrypt as _bcrypt
from anthropic import Anthropic
from dotenv import load_dotenv

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
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except Exception:
                pass

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
def _odoo_common():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)

def _odoo_object():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

def odoo_get_admin_uid() -> int | None:
    try:
        uid = _odoo_common().authenticate(ODOO_DB, ODOO_ADMIN, ODOO_PASS, {})
        return uid if uid else None
    except Exception as e:
        print(f"[Odoo] admin auth error: {e}")
        return None

def odoo_authenticate(email: str, password: str) -> int | None:
    """Returns Odoo UID on success, None on failure."""
    try:
        uid = _odoo_common().authenticate(ODOO_DB, email, password, {})
        return uid if uid else None
    except Exception:
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
        print(f"[Odoo] create user error: {e}")
        return None

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
    except Exception:
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

@app.get("/health")
def health():
    admin_uid = odoo_get_admin_uid()
    return {
        "status": "ok",
        "ai_ready":   bool(ANT_KEY),
        "odoo_live":  bool(admin_uid),
        "odoo_url":   ODOO_URL,
        "odoo_db":    ODOO_DB,
    }

@app.post("/api/v1/auth/signup")
def signup(req: SignupReq):
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
