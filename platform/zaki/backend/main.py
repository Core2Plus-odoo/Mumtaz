"""
ZAKI AI CFO — backend (zaki.mumtaz.digital)

Reads the tenant's live financial snapshot from their Odoo (via the
mumtaz_zaki `zaki.connector` bridge over XML-RPC), blends in the tenant's
knowledge base (zaki_kb in mumtaz_platform), and streams CFO-grade output
from Claude (official Anthropic SDK). Voice via ElevenLabs.

Secrets/config come from /opt/mumtaz/.env — nothing hardcoded.

SECURITY: every tenant-scoped route is authenticated and fails closed. A
caller must present ``Authorization: Bearer <token>`` that is either the shared
``ZAKI_SERVICE_TOKEN`` (trusted server-to-server) or a platform-issued HS256
JWT whose tenant claim matches the requested ``tenant_id`` (per-tenant
isolation — blocks tenant-ID enumeration / IDOR). If neither secret is
configured the routes refuse with 503, unless ``ZAKI_ALLOW_ANON=1`` is set to
explicitly restore the legacy open behaviour for local/dev use. CORS only
enables credentials when an explicit origin allowlist is configured (never the
``*`` + credentials anti-pattern).
"""
import hmac
import json
import os
import xmlrpc.client
from datetime import datetime

import asyncpg
import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv("/opt/mumtaz/.env")

DB_DSN = (f"postgresql://{os.environ.get('DB_USER','mumtaz_admin')}:"
          f"{os.environ.get('DB_PASS','')}@{os.environ.get('DB_HOST','localhost')}:"
          f"{os.environ.get('DB_PORT','5432')}/{os.environ.get('DB_NAME','mumtaz_platform')}")
ODOO_URL   = os.environ.get("ODOO_URL", "http://127.0.0.1:8069")
ODOO_DB_FALLBACK = os.environ.get("ODOO_DB", "")
ODOO_USER  = os.environ.get("ODOO_ADMIN_EMAIL", "admin")
ODOO_PASS  = os.environ.get("ODOO_ADMIN_PASS", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
EL_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
EL_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

# ── auth / CORS config ───────────────────────────────────────────────
PLATFORM_JWT_SECRET = os.environ.get("PLATFORM_JWT_SECRET", "")
PLATFORM_JWT_ALG    = os.environ.get("PLATFORM_JWT_ALG", "HS256")
ZAKI_SERVICE_TOKEN  = os.environ.get("ZAKI_SERVICE_TOKEN", "")
ALLOW_ANON = os.environ.get("ZAKI_ALLOW_ANON", "0") == "1"

# Only pair credentials with an explicit allowlist — "*" + credentials is
# invalid and browsers reject it. These APIs are Bearer-token, not cookie, so
# credentials are off unless origins are pinned.
_cors_explicit = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
CORS = _cors_explicit or ["*"]
ALLOW_CREDS = bool(_cors_explicit)

app = FastAPI(title="ZAKI AI CFO", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS, allow_credentials=ALLOW_CREDS,
                   allow_methods=["*"], allow_headers=["*"])
_pool: asyncpg.Pool | None = None
_ai = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


@app.on_event("startup")
async def _startup():
    global _pool
    _pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


# ── data helpers ─────────────────────────────────────────────────────
ZERO = {"monthly_revenue": 0, "monthly_expenses": 0, "net_profit": 0, "net_margin": 0,
        "cash": 0, "cash_runway": 0, "ar_total": 0, "ar_overdue": 0, "top_overdue": [],
        "payroll": 0, "payroll_pct": 0, "pipeline": 0, "timestamp": datetime.now().isoformat()}


async def get_tenant(tenant_id: int) -> dict | None:
    async with _pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT id,name,odoo_db,country,currency,industry,status FROM tenants WHERE id=$1",
            tenant_id)
        return dict(row) if row else None


def _odoo_snapshot_sync(odoo_db: str) -> dict:
    """Blocking XML-RPC call to the tenant's Odoo zaki.connector bridge."""
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(odoo_db, ODOO_USER, ODOO_PASS, {})
        if not uid:
            return dict(ZERO)
        obj = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
        snap = obj.execute_kw(odoo_db, uid, ODOO_PASS, "zaki.connector", "get_snapshot", [])
        return snap or dict(ZERO)
    except Exception:
        return dict(ZERO)


async def get_odoo_snapshot(tenant_id: int) -> dict:
    t = await get_tenant(tenant_id)
    db = (t or {}).get("odoo_db") or ODOO_DB_FALLBACK
    if not db:
        return dict(ZERO)
    import asyncio
    return await asyncio.to_thread(_odoo_snapshot_sync, db)


async def get_kb_context(tenant_id: int, max_chars: int = 1500) -> str:
    async with _pool.acquire() as c:
        rows = await c.fetch(
            "SELECT title,content FROM zaki_kb WHERE tenant_id=$1 AND archived=FALSE "
            "ORDER BY importance DESC, updated_at DESC LIMIT 20", tenant_id)
    out, total = [], 0
    for r in rows:
        line = f"- {r['title']}: {r['content']}"
        if total + len(line) > max_chars:
            break
        out.append(line); total += len(line)
    return "\n".join(out)


def _money(v, cur):
    return f"{cur} {float(v or 0):,.0f}"


def build_prompt(cfg: dict, snap: dict, kb: str) -> str:
    cur = cfg.get("currency", "AED"); first = cfg.get("first_name", "there")
    margin = snap.get("net_margin", 0); runway = snap.get("cash_runway", 0)
    prof = "STRONG" if margin >= 15 else "OK" if margin >= 5 else "WEAK"
    liq = "HEALTHY" if runway >= 90 else "LOW" if runway >= 45 else "CRITICAL"
    coll = "POOR" if (snap.get("ar_overdue", 0) or 0) > 0.2 * (snap.get("ar_total", 1) or 1) else "OK"
    top = "\n".join(f"  · {o['partner']} {_money(o['amount'],cur)} ({o['days_late']}d late)"
                    for o in (snap.get("top_overdue") or [])[:3]) or "  · none"
    kb_block = ("KNOWN FACTS:\n" + kb) if kb else ""
    return f"""You are ZAKI ذكي — elite AI CFO for {cfg.get('company_name','the company')}.
1. Always call the CEO '{first}' — never 'you' or 'the CEO'.
2. Always say 'we' and 'our' — never 'your company'.
3. Take clear, direct positions — never hedge.
4. Push back firmly when the numbers don't support what {first} wants.
5. Proactively flag risks and opportunities before being asked.
6. Always reference specific numbers — never say 'significant'.
7. Warm when things are good; direct and serious when they are not.
8. Never open with 'Great question', 'Certainly', or filler.
9. Sound like a trusted CFO over 7am coffee — not a board deck.
10. You ARE the financial advisor. Never say 'consult a professional.'

LIVE FINANCIALS (this month):
Revenue: {_money(snap.get('monthly_revenue'),cur)} | Expenses: {_money(snap.get('monthly_expenses'),cur)}
Net: {_money(snap.get('net_profit'),cur)} ({margin}% margin)
Cash: {_money(snap.get('cash'),cur)} — {runway} days runway
AR total: {_money(snap.get('ar_total'),cur)} | AR overdue: {_money(snap.get('ar_overdue'),cur)}
Top overdue:
{top}
Payroll: {_money(snap.get('payroll'),cur)} ({snap.get('payroll_pct',0)}% of revenue)
Pipeline: {_money(snap.get('pipeline'),cur)}

HEALTH: Profitability {prof} · Liquidity {liq} · Collections {coll}
CONTEXT: {cfg.get('industry','Trading')} business in {cfg.get('country','UAE')}.
{kb_block}"""


async def _stream(system: str, messages: list, max_tokens: int = 700):
    async def gen():
        try:
            async with _ai.messages.stream(model=ANTHROPIC_MODEL, max_tokens=max_tokens,
                                           system=system, messages=messages) as s:
                async for text in s.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'text': '⚠️ ZAKI is briefly unavailable. Please retry.'})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


# ── models ───────────────────────────────────────────────────────────
class BriefReq(BaseModel):
    tenant_id: int
    company_name: str = ""; ceo_name: str = ""; first_name: str = "there"
    industry: str = "Trading"; country: str = "UAE"; currency: str = "AED"; worries: str = ""

class ChatReq(BriefReq):
    message: str = ""
    history: list = []

class VoiceReq(BaseModel):
    text: str
    voice_id: str | None = None

class KBReq(BaseModel):
    tenant_id: int; category: str = "note"; title: str = ""; content: str = ""
    importance: int = 2; source: str = "chat"


def _verify(authorization: str | None, tenant_id: int | None = None) -> int | None:
    """Authenticate a request and enforce tenant isolation. Fails closed.

    Returns the authenticated tenant id (or ``None`` for a service token, which
    has cross-tenant access). Raises 401/403/503 on any failure. When a
    ``tenant_id`` is supplied and the caller presents a per-tenant JWT, the
    token's tenant claim MUST match — this is what blocks tenant-ID enumeration.
    """
    if ALLOW_ANON:
        return tenant_id
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    token = authorization[7:].strip()

    # Trusted server-to-server shared secret (constant-time compare).
    if ZAKI_SERVICE_TOKEN and hmac.compare_digest(token, ZAKI_SERVICE_TOKEN):
        return tenant_id

    # Platform-issued per-tenant JWT.
    if PLATFORM_JWT_SECRET:
        try:
            import jwt  # PyJWT — lazy so the service-token path needs no dep
            claims = jwt.decode(token, PLATFORM_JWT_SECRET, algorithms=[PLATFORM_JWT_ALG])
        except Exception:
            raise HTTPException(401, "Invalid or expired token")
        claim = claims.get("tenant_id", claims.get("tid", claims.get("sub")))
        try:
            tok_tid = int(claim)
        except (TypeError, ValueError):
            raise HTTPException(403, "Token has no tenant claim")
        if tenant_id is not None and tok_tid != int(tenant_id):
            raise HTTPException(403, "Token is not valid for this tenant")
        return tok_tid

    # Nothing to verify against and anon not permitted → refuse.
    raise HTTPException(503, "Authentication is not configured")


# ── routes ───────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "ZAKI AI CFO", "version": "2.0",
            "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/financials/{tenant_id}")
async def financials(tenant_id: int, authorization: str = Header(None)):
    _verify(authorization, tenant_id)
    return {"status": "ok", "data": await get_odoo_snapshot(tenant_id),
            "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/briefing/stream")
async def briefing(req: BriefReq, authorization: str = Header(None)):
    _verify(authorization, req.tenant_id)
    snap = await get_odoo_snapshot(req.tenant_id)
    kb = await get_kb_context(req.tenant_id)
    system = build_prompt(req.model_dump(), snap, kb)
    user = (f"Generate my morning briefing for {req.first_name}. Start with "
            f"'Good morning, {req.first_name}.' Cover: the #1 financial highlight, "
            f"the biggest risk today, the AR to chase (name the debtor), cash-runway "
            f"status, and one strategic priority for today. 150-200 words, flowing "
            f"paragraphs, specific numbers, direct.")
    return await _stream(system, [{"role": "user", "content": user}], 700)


@app.post("/api/v1/chat/stream")
async def chat(req: ChatReq, authorization: str = Header(None)):
    _verify(authorization, req.tenant_id)
    # Auto-capture salient statements to the KB.
    if any(k in req.message.lower() for k in ("decided", "client", "worried", "plan to",
                                              "signed", "agreed")):
        try:
            async with _pool.acquire() as c:
                await c.execute(
                    "INSERT INTO zaki_kb (tenant_id,category,title,content,importance,source)"
                    " VALUES ($1,'note',$2,$3,2,'chat')",
                    req.tenant_id, req.message[:80], req.message)
        except Exception:
            pass
    snap = await get_odoo_snapshot(req.tenant_id)
    kb = await get_kb_context(req.tenant_id)
    system = build_prompt(req.model_dump(), snap, kb)
    msgs = (req.history or [])[-10:] + [{"role": "user", "content": req.message}]
    return await _stream(system, msgs, 600)


@app.post("/api/v1/voice")
async def voice(req: VoiceReq, authorization: str = Header(None)):
    _verify(authorization)  # any valid credential — stops open ElevenLabs abuse
    if not EL_KEY:
        raise HTTPException(503, "Voice not configured")
    vid = req.voice_id or EL_VOICE
    async def gen():
        async with httpx.AsyncClient(timeout=60) as cli:
            async with cli.stream("POST",
                f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
                json={"text": req.text, "model_id": "eleven_turbo_v2",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}) as r:
                async for chunk in r.aiter_bytes():
                    yield chunk
    return StreamingResponse(gen(), media_type="audio/mpeg")


@app.get("/api/v1/health-score/{tenant_id}")
async def health_score(tenant_id: int, authorization: str = Header(None)):
    _verify(authorization, tenant_id)
    s = await get_odoo_snapshot(tenant_id)
    margin = s.get("net_margin", 0); runway = s.get("cash_runway", 0)
    ar_t = s.get("ar_total", 0) or 0; ar_o = s.get("ar_overdue", 0) or 0
    pp = s.get("payroll_pct", 0)
    profitability = min(100, max(0, margin * 4 + 40))
    liquidity = min(100, max(0, (runway / 90) * 70 + 10))
    collections = min(100, max(0, 100 - (ar_o / max(ar_t, 1)) * 100))
    payroll_score = min(100, max(0, 100 - (pp / 60) * 40))
    score = round((profitability + liquidity + collections + payroll_score) / 4)
    interp = ("Excellent" if score >= 80 else "Good" if score >= 65 else
              "Fair" if score >= 45 else "Needs Attention" if score >= 30 else "Critical")
    return {"score": score, "interpretation": interp, "breakdown": {
        "profitability": round(profitability), "liquidity": round(liquidity),
        "collections": round(collections), "payroll_score": round(payroll_score)},
        "snapshot": s}


@app.get("/api/v1/opportunities/{tenant_id}")
async def opportunities(tenant_id: int, authorization: str = Header(None)):
    _verify(authorization, tenant_id)
    s = await get_odoo_snapshot(tenant_id)
    cur = "AED"; out = []
    if (s.get("ar_overdue", 0) or 0) > 0:
        out.append({"type": "collections", "title": "Collect overdue receivables",
                    "impact": s["ar_overdue"], "effort": "Low", "confidence": 90,
                    "action": f"Chase {_money(s['ar_overdue'],cur)} in overdue AR this week."})
    if (s.get("net_margin", 0) or 0) < 10 and (s.get("monthly_expenses", 0) or 0) > 0:
        out.append({"type": "cost", "title": "Margin is thin — trim costs",
                    "impact": s["monthly_expenses"] * 0.1, "effort": "Medium", "confidence": 70,
                    "action": "Review top expense lines; a 10% cut materially lifts margin."})
    if (s.get("cash_runway", 999) or 999) < 90:
        out.append({"type": "liquidity", "title": "Shore up runway",
                    "impact": s.get("cash", 0), "effort": "Medium", "confidence": 75,
                    "action": "Consider invoice financing on the overdue AR to extend runway."})
    if (s.get("payroll_pct", 0) or 0) > 50:
        out.append({"type": "efficiency", "title": "Payroll ratio is high",
                    "impact": s.get("payroll", 0) * 0.15, "effort": "High", "confidence": 60,
                    "action": "Payroll exceeds 50% of revenue — review capacity vs output."})
    out.sort(key=lambda o: o["impact"], reverse=True)
    return {"opportunities": out, "currency": cur}


@app.post("/api/v1/kb/save")
async def kb_save(req: KBReq, authorization: str = Header(None)):
    _verify(authorization, req.tenant_id)
    async with _pool.acquire() as c:
        rid = await c.fetchval(
            "INSERT INTO zaki_kb (tenant_id,category,title,content,importance,source)"
            " VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
            req.tenant_id, req.category, req.title, req.content, req.importance, req.source)
    return {"status": "ok", "id": rid}


@app.get("/api/v1/kb/{tenant_id}")
async def kb_list(tenant_id: int, authorization: str = Header(None)):
    _verify(authorization, tenant_id)
    async with _pool.acquire() as c:
        rows = await c.fetch(
            "SELECT id,category,title,content,importance,updated_at FROM zaki_kb "
            "WHERE tenant_id=$1 AND archived=FALSE ORDER BY importance DESC, updated_at DESC",
            tenant_id)
    return {"entries": [dict(r) for r in rows]}


@app.delete("/api/v1/kb/{entry_id}")
async def kb_delete(entry_id: int, authorization: str = Header(None)):
    tid = _verify(authorization)
    async with _pool.acquire() as c:
        if tid is not None:  # per-tenant caller: only their own entries
            await c.execute("UPDATE zaki_kb SET archived=TRUE WHERE id=$1 AND tenant_id=$2",
                            entry_id, tid)
        else:  # service token / anon: cross-tenant
            await c.execute("UPDATE zaki_kb SET archived=TRUE WHERE id=$1", entry_id)
    return {"status": "ok"}
