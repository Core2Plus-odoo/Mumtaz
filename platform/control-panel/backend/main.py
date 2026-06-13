"""
Mumtaz Control Panel — backend (app.mumtaz.digital)

One codebase, two roles (super-admin sees all tenants; tenant-admin sees only
their own — decided by the JWT). Runs on the mumtaz_platform schema. Products
& pricing are read from the dynamic module_catalogue table (never hardcoded).
Secrets/config from /opt/mumtaz/.env.
"""
import asyncio
import os
import re
import secrets as _secrets
import time
from datetime import date, datetime, timedelta

import asyncpg
import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from pydantic import BaseModel

load_dotenv("/opt/mumtaz/.env")

DB_DSN = (f"postgresql://{os.environ.get('DB_USER','mumtaz_admin')}:"
          f"{os.environ.get('DB_PASS','')}@{os.environ.get('DB_HOST','localhost')}:"
          f"{os.environ.get('DB_PORT','5432')}/{os.environ.get('DB_NAME','mumtaz_platform')}")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure")
JWT_EXP    = int(os.environ.get("JWT_EXPIRY_SECONDS", "86400"))
ALGO       = "HS256"
ERP_URL    = os.environ.get("ERP_URL", "https://erp.mumtaz.digital")
ZAKI_URL   = os.environ.get("ZAKI_URL", "https://zaki.mumtaz.digital")
OWNERS     = {e.strip().lower() for e in os.environ.get("MUMTAZ_OWNERS", "").split(",") if e.strip()}
OWNERS.add("umer@mumtaz.digital")
CORS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()] or ["*"]
ODOO_BIN  = os.environ.get("ODOO_BIN", "odoo")
ODOO_CONF = os.environ.get("ODOO_CONF", "/etc/odoo/odoo.conf")
FREE_KEYS = ("einvoicing", "crm")
# Core ERP every new tenant is provisioned with (mapped to Odoo Community apps
# via module_catalogue.odoo_module). Billing still follows each module's price.
CORE_ERP_KEYS = ("einvoicing", "crm", "accounting", "sales", "inventory", "hr_payroll", "projects")

app = FastAPI(title="Mumtaz Control Panel", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
_pool: asyncpg.Pool | None = None


@app.on_event("startup")
async def _startup():
    global _pool
    _pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


# ── helpers ──────────────────────────────────────────────────────────
def make_jwt(payload: dict) -> str:
    p = dict(payload); p["exp"] = int(time.time()) + JWT_EXP
    # python-jose enforces RFC 7519: the "sub" claim MUST be a string. Our user
    # ids are ints, so stringify here and convert back in current_user().
    if "sub" in p and p["sub"] is not None:
        p["sub"] = str(p["sub"])
    return jwt.encode(p, JWT_SECRET, algorithm=ALGO)

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()

def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False

def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return (s or "tenant")[:60]

async def current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    try:
        data = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[ALGO])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    # "sub" is stored as a string in the token (RFC 7519 / python-jose); the rest
    # of the code expects the numeric user id, so coerce it back to int.
    if data.get("sub") is not None:
        try:
            data["sub"] = int(data["sub"])
        except (TypeError, ValueError):
            pass
    return data

async def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user.get("is_super_admin"):
        raise HTTPException(403, "Super-admin access required")
    return user

async def tenant_mrr(conn, tenant_id: int) -> float:
    v = await conn.fetchval(
        "SELECT COALESCE(SUM(mc.price_usd),0) FROM tenant_modules tm "
        "JOIN module_catalogue mc ON mc.id=tm.module_id "
        "WHERE tm.tenant_id=$1 AND tm.status='active' AND mc.is_free=FALSE", tenant_id)
    return float(v or 0)

async def log(conn, tenant_id, user_id, action, etype=None, eid=None, details=None, ip=None):
    import json as _j
    try:
        await conn.execute(
            "INSERT INTO activity_log (tenant_id,user_id,action,entity_type,entity_id,details,ip_address)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7)",
            tenant_id, user_id, action, etype, str(eid) if eid else None,
            _j.dumps(details or {}), ip)
    except Exception:
        pass

async def user_with_tenant(conn, email: str):
    return await conn.fetchrow("""
        SELECT u.*, t.name AS tenant_name, t.slug AS tenant_slug, t.type AS tenant_type,
               t.status AS tenant_status, t.odoo_db, t.plan AS tenant_plan
        FROM platform_users u LEFT JOIN tenants t ON t.id=u.tenant_id
        WHERE lower(u.email)=lower($1) AND u.status='active'""", email)

def public_user(row) -> dict:
    email = (row["email"] or "").lower()
    return {"id": row["id"], "email": row["email"], "name": row["name"],
            "first_name": row["first_name"], "role": row["role"],
            "is_super_admin": bool(row["is_super_admin"]) or email in OWNERS,
            "tenant_id": row["tenant_id"], "tenant_name": row["tenant_name"],
            "tenant_slug": row["tenant_slug"], "tenant_type": row["tenant_type"],
            "tenant_plan": row["tenant_plan"]}


# ── AUTH ─────────────────────────────────────────────────────────────
class LoginReq(BaseModel):
    email: str; password: str

@app.post("/api/v1/auth/login")
async def login(req: LoginReq, request: Request):
    async with _pool.acquire() as c:
        row = await user_with_tenant(c, req.email)
        if not row or not check_pw(req.password, row["password_hash"]):
            raise HTTPException(401, "Invalid email or password")
        await c.execute("UPDATE platform_users SET last_login=NOW() WHERE id=$1", row["id"])
        u = public_user(row)
        await log(c, u["tenant_id"], u["id"], "user_login", ip=request.client.host if request.client else None)
    token = make_jwt({"sub": u["id"], "tenant_id": u["tenant_id"],
                      "is_super_admin": u["is_super_admin"], "role": u["role"],
                      "email": u["email"], "name": u["name"], "first_name": u["first_name"]})
    return {"access_token": token, "token_type": "bearer", "user": u}

@app.get("/api/v1/auth/me")
async def me(user: dict = Depends(current_user)):
    async with _pool.acquire() as c:
        row = await user_with_tenant(c, user["email"])
        if not row:
            raise HTTPException(404, "User not found")
        return public_user(row)

@app.post("/api/v1/auth/logout")
async def logout(user: dict = Depends(current_user)):
    async with _pool.acquire() as c:
        await log(c, user.get("tenant_id"), user.get("sub"), "user_logout")
    return {"status": "ok"}

class PwReq(BaseModel):
    current_password: str; new_password: str

@app.post("/api/v1/auth/change-password")
async def change_pw(req: PwReq, user: dict = Depends(current_user)):
    if len(req.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    async with _pool.acquire() as c:
        row = await c.fetchrow("SELECT password_hash FROM platform_users WHERE id=$1", user["sub"])
        if not row or not check_pw(req.current_password, row["password_hash"]):
            raise HTTPException(403, "Current password is incorrect")
        await c.execute("UPDATE platform_users SET password_hash=$1 WHERE id=$2",
                        hash_pw(req.new_password), user["sub"])
    return {"status": "ok"}


# ── PUBLIC ───────────────────────────────────────────────────────────
@app.get("/api/v1/public/catalogue")
async def public_catalogue():
    async with _pool.acquire() as c:
        rows = await c.fetch(
            "SELECT key,name,description,icon,category,price_usd,price_aed,is_free,is_core "
            "FROM module_catalogue WHERE active=TRUE ORDER BY sort_order")
    return {"modules": [dict(r) | {"price_usd": float(r["price_usd"]),
                                   "price_aed": float(r["price_aed"])} for r in rows]}

class ContactReq(BaseModel):
    name: str = ""; email: str = ""; company: str = ""; country: str = ""; message: str = ""

@app.post("/api/v1/public/contact")
async def contact(req: ContactReq):
    async with _pool.acquire() as c:
        await log(c, None, None, "contact_form", "lead", None, req.model_dump())
    return {"status": "ok"}

class SignupReq(BaseModel):
    company_name: str; email: str; password: str
    name: str = ""; country: str = "UAE"; currency: str = "AED"; plan: str = "starter"

@app.post("/api/v1/public/signup")
async def signup(req: SignupReq):
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    async with _pool.acquire() as c:
        exists = await c.fetchval("SELECT 1 FROM platform_users WHERE lower(email)=lower($1)", req.email)
        if exists:
            raise HTTPException(409, "An account with this email already exists")
        base = slugify(req.company_name); slug = base; i = 1
        while await c.fetchval("SELECT 1 FROM tenants WHERE slug=$1", slug):
            i += 1; slug = f"{base}{i}"
        tid = await c.fetchval("""
            INSERT INTO tenants (slug,name,type,status,plan,country,currency,trial_ends_at,odoo_db)
            VALUES ($1,$2,'business','trial',$3,$4,$5,NOW()+INTERVAL '14 days',$6) RETURNING id""",
            slug, req.company_name, req.plan, req.country, req.currency, f"corp_{slug}")
        uid = await c.fetchval("""
            INSERT INTO platform_users (tenant_id,email,name,first_name,password_hash,role)
            VALUES ($1,$2,$3,$4,$5,'owner') RETURNING id""",
            tid, req.email, req.name or req.company_name,
            (req.name or req.company_name).split(" ")[0], hash_pw(req.password))
        await c.execute("""INSERT INTO tenant_modules (tenant_id,module_id)
            SELECT $1,id FROM module_catalogue WHERE key = ANY($2::text[]) ON CONFLICT DO NOTHING""",
            tid, list(CORE_ERP_KEYS))
        await log(c, tid, uid, "tenant_signup", "tenant", tid)
        row = await user_with_tenant(c, req.email)
    u = public_user(row)
    token = make_jwt({"sub": u["id"], "tenant_id": u["tenant_id"], "is_super_admin": u["is_super_admin"],
                      "role": u["role"], "email": u["email"], "name": u["name"], "first_name": u["first_name"]})
    return {"access_token": token, "token_type": "bearer", "user": u}


# ── ADMIN: analytics ─────────────────────────────────────────────────
@app.get("/api/v1/admin/overview")
async def admin_overview(_: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        async def n(q): return await c.fetchval(q) or 0
        total = await n("SELECT COUNT(*) FROM tenants")
        active = await n("SELECT COUNT(*) FROM tenants WHERE status='active'")
        trial = await n("SELECT COUNT(*) FROM tenants WHERE status='trial'")
        suspended = await n("SELECT COUNT(*) FROM tenants WHERE status='suspended'")
        users = await n("SELECT COUNT(*) FROM platform_users")
        biz = await n("SELECT COUNT(*) FROM tenants WHERE type='business'")
        org = await n("SELECT COUNT(*) FROM tenants WHERE type='org'")
        mrr = await c.fetchval(
            "SELECT COALESCE(SUM(mc.price_usd),0) FROM tenant_modules tm "
            "JOIN module_catalogue mc ON mc.id=tm.module_id "
            "JOIN tenants t ON t.id=tm.tenant_id "
            "WHERE tm.status='active' AND mc.is_free=FALSE AND t.status IN ('active','trial')") or 0
        plan_rows = await c.fetch("SELECT COALESCE(plan,'starter') p, COUNT(*) ct FROM tenants GROUP BY p")
        mods = await n("SELECT COUNT(*) FROM tenant_modules WHERE status='active'")
    return {"tenants": {"total": total, "active": active, "trial": trial, "suspended": suspended,
                        "business": biz, "org": org},
            "users": users, "mrr_usd": round(float(mrr), 2), "arr_usd": round(float(mrr) * 12, 2),
            "active_modules": mods, "plans": {r["p"]: r["ct"] for r in plan_rows}}

@app.get("/api/v1/admin/analytics/growth")
async def admin_growth(_: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        rows = await c.fetch(
            "SELECT to_char(date_trunc('month',created_at),'YYYY-MM') m, COUNT(*) n "
            "FROM tenants GROUP BY 1 ORDER BY 1")
    cum = 0; out = []
    for r in rows:
        cum += r["n"]; out.append({"month": r["m"], "new": r["n"], "cumulative": cum})
    return {"growth": out}


# ── ADMIN: tenants ───────────────────────────────────────────────────
@app.get("/api/v1/admin/tenants")
async def admin_tenants(_: dict = Depends(require_admin), search: str = "", type: str = "",
                        status: str = "", page: int = 1, limit: int = 20):
    where, args = ["1=1"], []
    if search: args.append(f"%{search.lower()}%"); where.append(f"(lower(t.name) LIKE ${len(args)} OR t.slug LIKE ${len(args)})")
    if type:   args.append(type);   where.append(f"t.type=${len(args)}")
    if status: args.append(status); where.append(f"t.status=${len(args)}")
    w = " AND ".join(where)
    async with _pool.acquire() as c:
        total = await c.fetchval(f"SELECT COUNT(*) FROM tenants t WHERE {w}", *args)
        rows = await c.fetch(f"""
            SELECT t.*,
              (SELECT COUNT(*) FROM tenant_modules tm WHERE tm.tenant_id=t.id AND tm.status='active') mod_count,
              (SELECT COUNT(*) FROM platform_users u WHERE u.tenant_id=t.id) user_count,
              (SELECT COALESCE(SUM(mc.price_usd),0) FROM tenant_modules tm JOIN module_catalogue mc ON mc.id=tm.module_id
                 WHERE tm.tenant_id=t.id AND tm.status='active' AND mc.is_free=FALSE) mrr
            FROM tenants t WHERE {w} ORDER BY t.created_at DESC
            OFFSET {(max(page,1)-1)*limit} LIMIT {limit}""", *args)
    items = [dict(r) | {"mrr": float(r["mrr"] or 0)} for r in rows]
    return {"total": total, "page": page, "limit": limit, "items": items}

@app.get("/api/v1/admin/tenants/{tid}")
async def admin_tenant(tid: int, _: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        t = await c.fetchrow("SELECT * FROM tenants WHERE id=$1", tid)
        if not t: raise HTTPException(404, "Tenant not found")
        mods = await c.fetch("""SELECT mc.key,mc.name,mc.icon,mc.price_usd,mc.is_free,tm.status,tm.activated_at
            FROM tenant_modules tm JOIN module_catalogue mc ON mc.id=tm.module_id
            WHERE tm.tenant_id=$1 ORDER BY mc.sort_order""", tid)
        users = await c.fetch("SELECT id,email,name,role,last_login FROM platform_users WHERE tenant_id=$1", tid)
        inv = await c.fetch("SELECT * FROM billing_invoices WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT 5", tid)
        act = await c.fetch("SELECT action,created_at FROM activity_log WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT 10", tid)
        mrr = await tenant_mrr(c, tid)
    return {"tenant": dict(t), "modules": [dict(m) | {"price_usd": float(m["price_usd"])} for m in mods],
            "users": [dict(u) for u in users], "invoices": [dict(i) for i in inv],
            "activity": [dict(a) for a in act], "mrr_usd": mrr}

class TenantReq(BaseModel):
    name: str; type: str = "business"; country: str = "UAE"; currency: str = "AED"
    industry: str = "Trading"; plan: str = "starter"
    owner_name: str = ""; owner_email: str = ""; owner_password: str = ""
    parent_org_id: int | None = None; add_free: bool = True

@app.post("/api/v1/admin/tenants")
async def admin_create_tenant(req: TenantReq, user: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        base = slugify(req.name); slug = base; i = 1
        while await c.fetchval("SELECT 1 FROM tenants WHERE slug=$1", slug):
            i += 1; slug = f"{base}{i}"
        prefix = "org_" if req.type in ("org",) else "corp_"
        tid = await c.fetchval("""
            INSERT INTO tenants (slug,name,type,status,plan,country,currency,industry,odoo_db,parent_org_id)
            VALUES ($1,$2,$3,'provisioning',$4,$5,$6,$7,$8,$9) RETURNING id""",
            slug, req.name, req.type, req.plan, req.country, req.currency, req.industry,
            f"{prefix}{slug}", req.parent_org_id)
        if req.owner_email:
            pw = req.owner_password or _secrets.token_urlsafe(10)
            await c.execute("""INSERT INTO platform_users (tenant_id,email,name,first_name,password_hash,role)
                VALUES ($1,$2,$3,$4,$5,'owner') ON CONFLICT (email) DO NOTHING""",
                tid, req.owner_email, req.owner_name or req.name,
                (req.owner_name or req.name).split(" ")[0], hash_pw(pw))
        if req.add_free:
            await c.execute("""INSERT INTO tenant_modules (tenant_id,module_id)
                SELECT $1,id FROM module_catalogue WHERE key=ANY($2::text[]) ON CONFLICT DO NOTHING""",
                tid, list(CORE_ERP_KEYS))
        await log(c, tid, user.get("sub"), "tenant_created", "tenant", tid)
        t = await c.fetchrow("SELECT * FROM tenants WHERE id=$1", tid)
    return {"tenant": dict(t)}

class TenantUpdate(BaseModel):
    name: str | None = None; plan: str | None = None; country: str | None = None
    currency: str | None = None; industry: str | None = None
    wl_name: str | None = None; wl_primary_color: str | None = None
    wl_secondary_color: str | None = None; wl_tagline: str | None = None; wl_subdomain: str | None = None

@app.put("/api/v1/admin/tenants/{tid}")
async def admin_update_tenant(tid: int, req: TenantUpdate, user: dict = Depends(require_admin)):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields: return {"status": "ok"}
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(fields))
    async with _pool.acquire() as c:
        await c.execute(f"UPDATE tenants SET {sets}, updated_at=NOW() WHERE id=$1", tid, *fields.values())
        await log(c, tid, user.get("sub"), "tenant_updated", "tenant", tid, fields)
        t = await c.fetchrow("SELECT * FROM tenants WHERE id=$1", tid)
    return {"tenant": dict(t)}

async def _set_status(tid, status, action, user, extra=""):
    async with _pool.acquire() as c:
        await c.execute(f"UPDATE tenants SET status=$1{extra} WHERE id=$2", status, tid)
        await log(c, tid, user.get("sub"), action, "tenant", tid)
        t = await c.fetchrow("SELECT * FROM tenants WHERE id=$1", tid)
    return {"tenant": dict(t)}

@app.post("/api/v1/admin/tenants/{tid}/suspend")
async def admin_suspend(tid: int, user: dict = Depends(require_admin)):
    return await _set_status(tid, "suspended", "tenant_suspended", user)

@app.post("/api/v1/admin/tenants/{tid}/activate")
async def admin_activate(tid: int, user: dict = Depends(require_admin)):
    return await _set_status(tid, "active", "tenant_activated", user, ", activated_at=NOW()")

@app.delete("/api/v1/admin/tenants/{tid}")
async def admin_cancel(tid: int, user: dict = Depends(require_admin)):
    return await _set_status(tid, "cancelled", "tenant_cancelled", user, ", cancelled_at=NOW()")

async def _provision(tid: int):
    async with _pool.acquire() as c:
        t = await c.fetchrow("SELECT slug,type,odoo_db FROM tenants WHERE id=$1", tid)
        if not t: return
        db = t["odoo_db"] or ((("org_" if t["type"] == "org" else "corp_")) + t["slug"])
        mods = await c.fetch("""SELECT mc.odoo_module FROM tenant_modules tm
            JOIN module_catalogue mc ON mc.id=tm.module_id
            WHERE tm.tenant_id=$1 AND tm.status='active' AND mc.odoo_module IS NOT NULL""", tid)
    install = ",".join(m["odoo_module"] for m in mods) or "base"
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-u", "odoo", ODOO_BIN, "-c", ODOO_CONF, "-d", db,
            "-i", install, "--without-demo=all", "--stop-after-init",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        ok = proc.returncode == 0
    except Exception:
        ok = False
    async with _pool.acquire() as c:
        await c.execute("UPDATE tenants SET odoo_db=$1, status=$2, activated_at=NOW() WHERE id=$3",
                        db, "active" if ok else "provisioning", tid)
        await log(c, tid, None, "odoo_provisioned" if ok else "odoo_provision_failed", "tenant", tid)

@app.post("/api/v1/admin/tenants/{tid}/provision-odoo")
async def admin_provision(tid: int, _: dict = Depends(require_admin)):
    asyncio.create_task(_provision(tid))
    return {"status": "provisioning", "message": "Odoo DB creation started in background"}


# ── Odoo module orchestration — install/uninstall apps in a tenant DB ─
# Each tenant_modules toggle (admin or tenant) is mirrored into the tenant's
# Odoo database here. Slow ops run in the background; a per-DB lock serialises
# concurrent toggles so two Odoo CLI runs never hit the same DB at once.
_odoo_locks: dict[str, asyncio.Lock] = {}

def _odoo_lock(db: str) -> asyncio.Lock:
    lk = _odoo_locks.get(db)
    if lk is None:
        lk = _odoo_locks[db] = asyncio.Lock()
    return lk

async def _odoo_run(db: str, args: list[str], stdin: bytes | None = None) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-u", "odoo", ODOO_BIN, *args, "-c", ODOO_CONF, "-d", db,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.communicate(stdin)
        return proc.returncode == 0
    except Exception:
        return False

async def _odoo_install(db: str, modules: list[str]) -> bool:
    if not modules:
        return True
    return await _odoo_run(db, ["-i", ",".join(modules), "--without-demo=all", "--stop-after-init"])

async def _odoo_uninstall(db: str, modules: list[str]) -> bool:
    if not modules:
        return True
    names = ",".join(repr(m) for m in modules)
    script = ("m=env['ir.module.module'].search("
              f"[('name','in',[{names}]),('state','=','installed')])\n"
              "m and m.button_immediate_uninstall()\n"
              "env.cr.commit()\n")
    return await _odoo_run(db, ["shell", "--no-http"], stdin=script.encode())

async def _sync_module_to_odoo(tid: int, key: str, install: bool):
    """Background: install/uninstall a catalogue module in the tenant's Odoo DB."""
    async with _pool.acquire() as c:
        db = await c.fetchval("SELECT odoo_db FROM tenants WHERE id=$1", tid)
        odoo_mod = await c.fetchval("SELECT odoo_module FROM module_catalogue WHERE key=$1", key)
    # Skip if the tenant has no provisioned DB yet, or the module has no Odoo
    # app mapping (provisioning will install whatever is active later).
    if not db or not odoo_mod:
        return
    modules = [m.strip() for m in odoo_mod.split(",") if m.strip()]
    async with _odoo_lock(db):
        ok = await (_odoo_install(db, modules) if install else _odoo_uninstall(db, modules))
    async with _pool.acquire() as c:
        if install and not ok:
            await c.execute(
                "UPDATE tenant_modules SET status='failed' WHERE tenant_id=$1 AND "
                "module_id=(SELECT id FROM module_catalogue WHERE key=$2)", tid, key)
        verb = ("installed" if install else "uninstalled") if ok else \
               ("install_failed" if install else "uninstall_failed")
        await log(c, tid, None, f"odoo_module_{verb}", "module", key)

@app.get("/api/v1/admin/tenants/{tid}/odoo-link")
async def admin_odoo_link(tid: int, _: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        db = await c.fetchval("SELECT odoo_db FROM tenants WHERE id=$1", tid)
    return {"url": f"{ERP_URL}/web?db={db or ''}"}

@app.post("/api/v1/admin/tenants/{tid}/impersonate")
async def admin_impersonate(tid: int, user: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        row = await c.fetchrow("""SELECT u.*,t.name tenant_name,t.slug tenant_slug,t.type tenant_type,
            t.plan tenant_plan FROM platform_users u JOIN tenants t ON t.id=u.tenant_id
            WHERE u.tenant_id=$1 ORDER BY u.id LIMIT 1""", tid)
        if not row: raise HTTPException(404, "No user for this tenant")
        await log(c, tid, user.get("sub"), "impersonate", "tenant", tid)
    u = public_user(row); u["is_super_admin"] = False
    token = make_jwt({"sub": u["id"], "tenant_id": tid, "is_super_admin": False, "role": u["role"],
                      "email": u["email"], "name": u["name"], "first_name": u["first_name"],
                      "impersonated_by": user.get("sub")})
    return {"access_token": token, "user": u}


# ── ADMIN: catalogue + modules ───────────────────────────────────────
@app.get("/api/v1/admin/modules")
async def admin_modules(_: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        rows = await c.fetch("""SELECT mc.*,
            (SELECT COUNT(*) FROM tenant_modules tm WHERE tm.module_id=mc.id AND tm.status='active') active_tenants
            FROM module_catalogue mc ORDER BY mc.sort_order""")
    return {"modules": [dict(r) | {"price_usd": float(r["price_usd"]), "price_aed": float(r["price_aed"]),
            "monthly_revenue": float(r["price_usd"]) * (r["active_tenants"] or 0)} for r in rows]}

class ModuleEdit(BaseModel):
    price_usd: float | None = None; price_aed: float | None = None
    active: bool | None = None; name: str | None = None; description: str | None = None

@app.put("/api/v1/admin/modules/{key}")
async def admin_edit_module(key: str, req: ModuleEdit, user: dict = Depends(require_admin)):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields: return {"status": "ok"}
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(fields))
    async with _pool.acquire() as c:
        await c.execute(f"UPDATE module_catalogue SET {sets} WHERE key=$1", key, *fields.values())
        await log(c, None, user.get("sub"), "module_edited", "module", key, fields)
    return {"status": "ok"}

async def _add_module(conn, tid, key):
    mid = await conn.fetchval("SELECT id FROM module_catalogue WHERE key=$1 AND active=TRUE", key)
    if not mid: raise HTTPException(404, "Unknown module")
    await conn.execute("INSERT INTO tenant_modules (tenant_id,module_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", tid, mid)

@app.post("/api/v1/admin/tenants/{tid}/modules")
async def admin_add_module(tid: int, body: dict, user: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        await _add_module(c, tid, body.get("module_key", ""))
        mrr = await tenant_mrr(c, tid); await c.execute("UPDATE tenants SET mrr_usd=$1 WHERE id=$2", mrr, tid)
        await log(c, tid, user.get("sub"), "module_activated", "module", body.get("module_key"))
    asyncio.create_task(_sync_module_to_odoo(tid, body.get("module_key", ""), install=True))
    return {"status": "ok", "mrr_usd": mrr}

@app.delete("/api/v1/admin/tenants/{tid}/modules/{key}")
async def admin_del_module(tid: int, key: str, user: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        core = await c.fetchval("SELECT is_core FROM module_catalogue WHERE key=$1", key)
        if core: raise HTTPException(400, "Core modules cannot be removed")
        await c.execute("""DELETE FROM tenant_modules WHERE tenant_id=$1 AND
            module_id=(SELECT id FROM module_catalogue WHERE key=$2)""", tid, key)
        mrr = await tenant_mrr(c, tid); await c.execute("UPDATE tenants SET mrr_usd=$1 WHERE id=$2", mrr, tid)
        await log(c, tid, user.get("sub"), "module_deactivated", "module", key)
    asyncio.create_task(_sync_module_to_odoo(tid, key, install=False))
    return {"status": "ok", "mrr_usd": mrr}


# ── ADMIN: billing ───────────────────────────────────────────────────
@app.get("/api/v1/admin/billing")
async def admin_billing(_: dict = Depends(require_admin), status: str = "", page: int = 1, limit: int = 30):
    where, args = ["1=1"], []
    if status: args.append(status); where.append(f"b.status=${len(args)}")
    w = " AND ".join(where)
    async with _pool.acquire() as c:
        total = await c.fetchval(f"SELECT COUNT(*) FROM billing_invoices b WHERE {w}", *args)
        rows = await c.fetch(f"""SELECT b.*, t.name tenant_name FROM billing_invoices b
            JOIN tenants t ON t.id=b.tenant_id WHERE {w} ORDER BY b.created_at DESC
            OFFSET {(max(page,1)-1)*limit} LIMIT {limit}""", *args)
    return {"total": total, "items": [dict(r) | {"amount_usd": float(r["amount_usd"])} for r in rows]}

@app.get("/api/v1/admin/billing/mrr")
async def admin_mrr(_: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        by_mod = await c.fetch("""SELECT mc.key, mc.price_usd*COUNT(*) rev FROM tenant_modules tm
            JOIN module_catalogue mc ON mc.id=tm.module_id JOIN tenants t ON t.id=tm.tenant_id
            WHERE tm.status='active' AND mc.is_free=FALSE AND t.status IN ('active','trial')
            GROUP BY mc.key, mc.price_usd""")
    total = sum(float(r["rev"]) for r in by_mod)
    return {"total_mrr_usd": round(total, 2), "arr_usd": round(total * 12, 2),
            "by_module": {r["key"]: float(r["rev"]) for r in by_mod}}

@app.post("/api/v1/admin/billing/run-monthly")
async def admin_run_billing(user: dict = Depends(require_admin)):
    today = date.today(); ps = today.replace(day=1)
    nxt = (ps + timedelta(days=32)).replace(day=1); pe = nxt - timedelta(days=1)
    created = 0; total = 0.0
    async with _pool.acquire() as c:
        tenants = await c.fetch("SELECT id FROM tenants WHERE status IN ('active','trial')")
        for t in tenants:
            amt = await tenant_mrr(c, t["id"])
            if amt <= 0: continue
            ref = f"INV-{today:%Y%m}-{t['id']}"
            await c.execute("""INSERT INTO billing_invoices (tenant_id,invoice_ref,amount_usd,period_start,period_end,due_date,status)
                VALUES ($1,$2,$3,$4,$5,$6,'pending') ON CONFLICT (invoice_ref) DO NOTHING""",
                t["id"], ref, amt, ps, pe, pe)
            await c.execute("UPDATE tenants SET mrr_usd=$1 WHERE id=$2", amt, t["id"])
            created += 1; total += amt
        await log(c, None, user.get("sub"), "billing_run", details={"created": created, "total": total})
    return {"invoices_created": created, "total_usd": round(total, 2)}

@app.put("/api/v1/admin/billing/{inv_id}/mark-paid")
async def admin_mark_paid(inv_id: int, user: dict = Depends(require_admin)):
    async with _pool.acquire() as c:
        await c.execute("UPDATE billing_invoices SET status='paid', paid_at=NOW() WHERE id=$1", inv_id)
        await log(c, None, user.get("sub"), "invoice_paid", "invoice", inv_id)
    return {"status": "ok"}

@app.get("/api/v1/admin/activity")
async def admin_activity(_: dict = Depends(require_admin), limit: int = 50):
    async with _pool.acquire() as c:
        rows = await c.fetch("""SELECT a.action,a.entity_type,a.created_at,a.details,
            t.name tenant_name, u.name user_name FROM activity_log a
            LEFT JOIN tenants t ON t.id=a.tenant_id LEFT JOIN platform_users u ON u.id=a.user_id
            ORDER BY a.created_at DESC LIMIT $1""", limit)
    return {"items": [dict(r) for r in rows]}


# ── TENANT (scoped to JWT tenant_id) ─────────────────────────────────
def _tid(user):
    t = user.get("tenant_id")
    if not t: raise HTTPException(400, "No tenant on this account")
    return t

@app.get("/api/v1/tenant/me")
async def tenant_me(user: dict = Depends(current_user)):
    async with _pool.acquire() as c:
        t = await c.fetchrow("SELECT * FROM tenants WHERE id=$1", _tid(user))
    return {"tenant": dict(t) if t else None}

@app.get("/api/v1/tenant/modules")
async def tenant_modules(user: dict = Depends(current_user)):
    tid = _tid(user)
    async with _pool.acquire() as c:
        active = await c.fetch("""SELECT mc.key,mc.name,mc.icon,mc.price_usd,mc.is_free,mc.is_core,tm.activated_at
            FROM tenant_modules tm JOIN module_catalogue mc ON mc.id=tm.module_id
            WHERE tm.tenant_id=$1 AND tm.status='active' ORDER BY mc.sort_order""", tid)
        akeys = [r["key"] for r in active]
        avail = await c.fetch("SELECT key,name,icon,description,price_usd,is_free FROM module_catalogue WHERE active=TRUE ORDER BY sort_order")
        mrr = await tenant_mrr(c, tid)
    return {"active": [dict(r) | {"price_usd": float(r["price_usd"])} for r in active],
            "available": [dict(r) | {"price_usd": float(r["price_usd"])} for r in avail if r["key"] not in akeys],
            "mrr_usd": mrr}

@app.post("/api/v1/tenant/modules/{key}/activate")
async def tenant_activate_module(key: str, user: dict = Depends(current_user)):
    tid = _tid(user)
    async with _pool.acquire() as c:
        await _add_module(c, tid, key)
        mrr = await tenant_mrr(c, tid); await c.execute("UPDATE tenants SET mrr_usd=$1 WHERE id=$2", mrr, tid)
        await log(c, tid, user.get("sub"), "module_activated", "module", key)
    asyncio.create_task(_sync_module_to_odoo(tid, key, install=True))
    return {"status": "ok", "mrr_usd": mrr}

@app.delete("/api/v1/tenant/modules/{key}")
async def tenant_deactivate_module(key: str, user: dict = Depends(current_user)):
    tid = _tid(user)
    async with _pool.acquire() as c:
        if await c.fetchval("SELECT is_core FROM module_catalogue WHERE key=$1", key):
            raise HTTPException(400, "Core modules cannot be removed")
        await c.execute("""DELETE FROM tenant_modules WHERE tenant_id=$1 AND
            module_id=(SELECT id FROM module_catalogue WHERE key=$2)""", tid, key)
        mrr = await tenant_mrr(c, tid); await c.execute("UPDATE tenants SET mrr_usd=$1 WHERE id=$2", mrr, tid)
        await log(c, tid, user.get("sub"), "module_deactivated", "module", key)
    asyncio.create_task(_sync_module_to_odoo(tid, key, install=False))
    return {"status": "ok", "mrr_usd": mrr}

@app.get("/api/v1/tenant/billing")
async def tenant_billing(user: dict = Depends(current_user)):
    async with _pool.acquire() as c:
        rows = await c.fetch("SELECT * FROM billing_invoices WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT 24", _tid(user))
    return {"items": [dict(r) | {"amount_usd": float(r["amount_usd"])} for r in rows]}

@app.get("/api/v1/tenant/users")
async def tenant_users(user: dict = Depends(current_user)):
    async with _pool.acquire() as c:
        rows = await c.fetch("SELECT id,email,name,role,last_login FROM platform_users WHERE tenant_id=$1", _tid(user))
    return {"users": [dict(r) for r in rows]}

class InviteReq(BaseModel):
    name: str; email: str; role: str = "member"

@app.post("/api/v1/tenant/users/invite")
async def tenant_invite(req: InviteReq, user: dict = Depends(current_user)):
    tid = _tid(user); tmp = _secrets.token_urlsafe(10)
    async with _pool.acquire() as c:
        if await c.fetchval("SELECT 1 FROM platform_users WHERE lower(email)=lower($1)", req.email):
            raise HTTPException(409, "Email already in use")
        uid = await c.fetchval("""INSERT INTO platform_users (tenant_id,email,name,first_name,password_hash,role)
            VALUES ($1,$2,$3,$4,$5,$6) RETURNING id""", tid, req.email, req.name,
            req.name.split(" ")[0], hash_pw(tmp), req.role)
        await log(c, tid, user.get("sub"), "user_invited", "user", uid)
    return {"status": "ok", "temp_password": tmp}

@app.get("/api/v1/tenant/odoo-link")
async def tenant_odoo_link(user: dict = Depends(current_user)):
    async with _pool.acquire() as c:
        db = await c.fetchval("SELECT odoo_db FROM tenants WHERE id=$1", _tid(user))
    return {"url": f"{ERP_URL}/web?db={db or ''}"}

@app.get("/api/v1/tenant/zaki-link")
async def tenant_zaki_link(user: dict = Depends(current_user)):
    return {"url": f"{ZAKI_URL}?tid={_tid(user)}"}

class SettingsReq(BaseModel):
    name: str | None = None; industry: str | None = None
    country: str | None = None; currency: str | None = None

@app.put("/api/v1/tenant/settings")
async def tenant_settings(req: SettingsReq, user: dict = Depends(current_user)):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields: return {"status": "ok"}
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(fields))
    async with _pool.acquire() as c:
        await c.execute(f"UPDATE tenants SET {sets}, updated_at=NOW() WHERE id=$1", _tid(user), *fields.values())
    return {"status": "ok"}

class WLReq(BaseModel):
    wl_name: str | None = None; wl_logo_url: str | None = None; wl_tagline: str | None = None
    wl_primary_color: str | None = None; wl_secondary_color: str | None = None; wl_subdomain: str | None = None

@app.put("/api/v1/tenant/whitelabel")
async def tenant_whitelabel(req: WLReq, user: dict = Depends(current_user)):
    tid = _tid(user)
    async with _pool.acquire() as c:
        if await c.fetchval("SELECT type FROM tenants WHERE id=$1", tid) != "org":
            raise HTTPException(403, "White-label is available to organisation tenants only")
        fields = {k: v for k, v in req.model_dump().items() if v is not None}
        if fields:
            sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(fields))
            await c.execute(f"UPDATE tenants SET {sets} WHERE id=$1", tid, *fields.values())
    return {"status": "ok"}

@app.get("/api/v1/tenant/org-network")
async def tenant_org_network(user: dict = Depends(current_user)):
    tid = _tid(user)
    async with _pool.acquire() as c:
        rows = await c.fetch("SELECT id,name,slug,status,country,plan,created_at FROM tenants WHERE parent_org_id=$1 ORDER BY created_at DESC", tid)
    return {"smes": [dict(r) for r in rows], "count": len(rows)}

class OrgSmeReq(BaseModel):
    name: str; country: str = "UAE"; owner_email: str = ""; owner_name: str = ""

@app.post("/api/v1/tenant/org-sme")
async def tenant_org_sme(req: OrgSmeReq, user: dict = Depends(current_user)):
    tid = _tid(user)
    async with _pool.acquire() as c:
        if await c.fetchval("SELECT type FROM tenants WHERE id=$1", tid) != "org":
            raise HTTPException(403, "Only organisations can add SMEs")
        base = slugify(req.name); slug = base; i = 1
        while await c.fetchval("SELECT 1 FROM tenants WHERE slug=$1", slug):
            i += 1; slug = f"{base}{i}"
        sid = await c.fetchval("""INSERT INTO tenants (slug,name,type,status,country,parent_org_id,odoo_db)
            VALUES ($1,$2,'org_sme','active',$3,$4,$5) RETURNING id""", slug, req.name, req.country, tid, f"orgsme_{slug}")
        if req.owner_email:
            await c.execute("""INSERT INTO platform_users (tenant_id,email,name,first_name,password_hash,role)
                VALUES ($1,$2,$3,$4,$5,'owner') ON CONFLICT (email) DO NOTHING""",
                sid, req.owner_email, req.owner_name or req.name, (req.owner_name or req.name).split(" ")[0],
                hash_pw(_secrets.token_urlsafe(10)))
        await c.execute("""INSERT INTO tenant_modules (tenant_id,module_id)
            SELECT $1,id FROM module_catalogue WHERE key=ANY($2::text[]) ON CONFLICT DO NOTHING""", sid, list(CORE_ERP_KEYS))
        await log(c, tid, user.get("sub"), "org_sme_created", "tenant", sid)
    return {"status": "ok", "sme_id": sid}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Mumtaz Control Panel", "version": "2.0"}
