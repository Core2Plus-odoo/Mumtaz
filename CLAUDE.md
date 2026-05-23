# Mumtaz Platform — AI Coding Governance

This file governs all AI-assisted development on the Mumtaz platform.
Claude must read and follow these rules before writing any code.

## Project Overview

Mumtaz is a **Multi-Tenant SaaS ERP** built on Odoo 19, with:
- **Zaki AI**: Claude-powered executive intelligence (Farid CFO + Ayaz Commercial agents)
- **Platform API**: FastAPI auth/billing/ZATCA backend (`apps/zaki-server/`)
- **Zaki-AI**: Node.js AI service (`apps/zaki-ai/`)
- **Marketplace**: B2B marketplace (`apps/marketplace/`)
- **29 custom Odoo addons** in `addons/`

**Target geography**: UAE / KSA / GCC
**Compliance**: ZATCA Phase 2 (KSA), UAE VAT, GDPR-adjacent

---

## ABSOLUTE RULES — Never violate

### 1. No secrets in code
Never hardcode API keys, passwords, JWT secrets, or credentials.
Use environment variables loaded via `python-dotenv` (Python) or `dotenv` (Node.js).
Never commit `.env` files — only `.env.example`.

### 2. No SQLite in production services
The platform database MUST use PostgreSQL (via `DATABASE_URL` env var).
SQLite is acceptable only for local development (`ENVIRONMENT=development`).
All database code MUST use `get_db()` from `apps/zaki-server/db.py`.

### 3. Tenant isolation is sacred
Every query that touches tenant data MUST be scoped to the correct tenant.
Never write `SELECT * FROM users` without a tenant/user filter.
The Odoo database name (`tenant_db`) must be validated before use.

### 4. Never expose internal errors to clients
Catch ALL exceptions at API boundaries.
Log full details with `print()` or logging internally.
Return generic messages externally: `{"error": "Service unavailable"}`.

### 5. All Odoo models use `mumtaz.` prefix
`mumtaz.tenant`, `mumtaz.setting`, etc.
NEVER modify core Odoo models directly — always use `_inherit`.
NEVER add Mumtaz-specific fields directly to `res.users`, `res.partner`, etc.

### 6. ZATCA compliance is non-negotiable
Any change to `addons/mumtaz_einvoicing/` requires cross-checking against
the ZATCA Phase 2 technical specification.
Never stub production ZATCA API calls.

### 7. ON CONFLICT syntax (not INSERT OR REPLACE/IGNORE)
Always use ANSI-compatible upsert syntax:
```sql
INSERT INTO t (col) VALUES (?) ON CONFLICT(col) DO UPDATE SET ...
INSERT INTO t (col) VALUES (?) ON CONFLICT(col) DO NOTHING
```
`INSERT OR REPLACE` and `INSERT OR IGNORE` are SQLite-only and break PostgreSQL.

---

## Code Style

### Python (FastAPI / Odoo addons)
- Formatter: `black` or `ruff format`
- Linter: `ruff check`
- Type hints required on all function signatures
- No bare `except:` — always catch specific exceptions or `except Exception as e:`
- Async: use `async/await` throughout FastAPI; never blocking I/O in async context
- Config: use `os.environ.get()` with explicit validation, or pydantic BaseSettings

### JavaScript / Node.js (Zaki-AI)
- `'use strict'` at top of every file
- `const`/`let` only — never `var`
- Error handling: always `try/catch` in async functions
- Logging: `console.error()` for errors, `console.warn()` for warnings

---

## Architecture Decisions

### Claude Model Selection
- **Routing** (single-word response): `claude-haiku-4-5` — fast + cheap
- **Agent analysis** (financial/commercial): `claude-opus-4-7` with `thinking: {type: "adaptive"}`
- **Background/batch**: `claude-sonnet-4-6`
- Never use model IDs with date suffixes (e.g. `claude-opus-4-7-20250514`)
- Always check `ZAKI_AGENT_MODEL` env var before hardcoding a model

### Database
- Platform metadata: PostgreSQL via `DATABASE_URL`
- Odoo tenant data: Per-tenant PostgreSQL DB (`mt_{slug}_{hex}`)
- Settings/config: `settings` table in platform DB (via `settings_store.py`)
- Never use SQLite in production

### API
- All routes under `/api/v1/` — no unversioned endpoints
- Always validate inputs with Pydantic models
- Return errors as `{"error": "...", "code": "SNAKE_CASE_CODE"}`

---

## Security Requirements

- Input validation: All API inputs validated with Pydantic before use
- SQL: Parameterized queries only — never f-string SQL
- CORS: Explicit allowlist from `CORS_ORIGINS` env var — never `["*"]`
- JWT: `JWT_SECRET` must be set; startup crashes if missing or default
- Prompt injection: All user messages pass through `middleware/sanitize.js`
- Security headers: Always include HSTS, X-Frame-Options, X-Content-Type-Options

---

## Git Commit Format

```
type(scope): subject

Types: feat | fix | refactor | test | docs | chore | security | perf
Scopes: platform | odoo | zaki-ai | marketplace | infra | deps

Examples:
  feat(platform): add refresh token endpoint
  fix(odoo): correct ZATCA TLV encoding for credit notes
  security(platform): replace SQLite with PostgreSQL
  perf(zaki-ai): use haiku for routing, opus for analysis
```

## Branch Strategy

- `main` → production (2 approvals required)
- `develop` → staging (auto-deploy)
- `feature/*` → new features, branch from `develop`
- `fix/*` → bug fixes
- `claude/*` → AI-assisted development branches

---

## Testing Minimum Bar

- New FastAPI endpoints: pytest test for success + auth failure cases
- New Odoo models: `TransactionCase` test for create + security
- New agent tools: Jest test for tool dispatcher
- Security-sensitive changes (auth, JWT, CORS): always test before merging

---

## Files Never to Modify Without Review

- `addons/mumtaz_einvoicing/` — ZATCA compliance, needs compliance review
- `apps/zaki-server/main.py` auth section — security-critical
- `docker-compose.production.yml` — production infra changes
- `config/nginx.conf` — traffic routing and rate limiting
