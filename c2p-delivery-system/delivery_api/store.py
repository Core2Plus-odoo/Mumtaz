"""Durable store (SQLite) — engagements, accounts, client knowledge, run log.

This is the API's working state. Odoo remains the system of record for business
objects (see sync.py); this is the index the app reads/writes on every request,
plus the owned datasets (knowledge + agent_runs) that compound over time. Point
C2P_STORE at a path on the VPS, or swap for Postgres (+ pgvector) later.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from models import Account, Engagement, KnowledgeEntry

DB_PATH = os.getenv("C2P_STORE", "delivery.db")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


_DDL = """
CREATE TABLE IF NOT EXISTS engagements (
  id            TEXT PRIMARY KEY,
  company       TEXT NOT NULL,
  odoo_db       TEXT,
  account_id    TEXT,
  crm_lead_id   INTEGER,
  sale_order_id INTEGER,
  project_id    INTEGER,
  created_at    TEXT,
  stages        TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  partner_id INTEGER,
  odoo_db    TEXT,
  industry   TEXT,
  country    TEXT,
  created_at TEXT,
  profile    TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS knowledge_entries (
  id         TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  kind       TEXT,
  title      TEXT,
  content    TEXT,
  learned_by TEXT,
  created_at TEXT,
  tags       TEXT NOT NULL DEFAULT '[]',
  searchable TEXT
);
CREATE INDEX IF NOT EXISTS ix_knowledge_account ON knowledge_entries(account_id);
CREATE TABLE IF NOT EXISTS agent_runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  task          TEXT,
  model         TEXT,
  account_id    TEXT,
  engagement_id TEXT,
  system        TEXT,
  input         TEXT,
  output        TEXT,
  raw_text      TEXT,
  input_tokens  INTEGER,
  output_tokens INTEGER,
  ms            INTEGER,
  error         TEXT,
  created_at    TEXT
);
"""


class EngagementStore:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        with self._conn() as c:
            c.executescript(_DDL)
            self._migrate(c)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _migrate(self, c: sqlite3.Connection) -> None:
        """Idempotent column adds for stores created before Phase 1."""
        cols = {r["name"] for r in c.execute("PRAGMA table_info(engagements)")}
        if "account_id" not in cols:
            c.execute("ALTER TABLE engagements ADD COLUMN account_id TEXT")

    # ── Engagements ──────────────────────────────────────────────────────
    def _to_eng(self, r: sqlite3.Row) -> Engagement:
        keys = r.keys()
        return Engagement(
            id=r["id"], company=r["company"], odoo_db=r["odoo_db"],
            account_id=(r["account_id"] if "account_id" in keys else None),
            crm_lead_id=r["crm_lead_id"], sale_order_id=r["sale_order_id"],
            project_id=r["project_id"], created_at=r["created_at"] or "",
            stages=json.loads(r["stages"] or "{}"),
        )

    def create(self, company: str, odoo_db: Optional[str],
               account_id: Optional[str] = None) -> Engagement:
        eng = Engagement(company=company, odoo_db=odoo_db, account_id=account_id)
        self.save(eng)
        return eng

    def save(self, eng: Engagement) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO engagements
                   (id, company, odoo_db, account_id, crm_lead_id, sale_order_id,
                    project_id, created_at, stages)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     company=excluded.company, odoo_db=excluded.odoo_db,
                     account_id=excluded.account_id,
                     crm_lead_id=excluded.crm_lead_id, sale_order_id=excluded.sale_order_id,
                     project_id=excluded.project_id, stages=excluded.stages""",
                (eng.id, eng.company, eng.odoo_db, eng.account_id, eng.crm_lead_id,
                 eng.sale_order_id, eng.project_id, eng.created_at, json.dumps(eng.stages)),
            )

    def get(self, eng_id: str) -> Optional[Engagement]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM engagements WHERE id=?", (eng_id,)).fetchone()
            return self._to_eng(r) if r else None

    def list(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, company, account_id, stages FROM engagements ORDER BY created_at DESC"
            ).fetchall()
            return [
                {"id": r["id"], "company": r["company"], "account_id": r["account_id"],
                 "stages": list(json.loads(r["stages"] or "{}"))}
                for r in rows
            ]

    # ── App settings (e.g. branding) ─────────────────────────────────────
    def get_setting(self, key: str) -> dict:
        with self._conn() as c:
            r = c.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
            return json.loads(r["value"]) if r and r["value"] else {}

    def save_setting(self, key: str, data: dict) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO app_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(data)),
            )

    # ── Accounts ─────────────────────────────────────────────────────────
    def _to_account(self, r: sqlite3.Row) -> Account:
        return Account(
            id=r["id"], name=r["name"], partner_id=r["partner_id"],
            odoo_db=r["odoo_db"], industry=r["industry"], country=r["country"],
            created_at=r["created_at"] or "", profile=json.loads(r["profile"] or "{}"),
        )

    def create_account(self, acc: Account) -> Account:
        with self._conn() as c:
            c.execute(
                """INSERT INTO accounts
                   (id, name, partner_id, odoo_db, industry, country, created_at, profile)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (acc.id, acc.name, acc.partner_id, acc.odoo_db, acc.industry,
                 acc.country, acc.created_at, json.dumps(acc.profile)),
            )
        return acc

    def get_account(self, account_id: str) -> Optional[Account]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
            return self._to_account(r) if r else None

    def get_account_by_partner(self, partner_id: int) -> Optional[Account]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM accounts WHERE partner_id=?", (partner_id,)).fetchone()
            return self._to_account(r) if r else None

    def update_account_profile(self, account_id: str, profile: dict) -> None:
        with self._conn() as c:
            c.execute("UPDATE accounts SET profile=? WHERE id=?",
                      (json.dumps(profile), account_id))

    def list_accounts(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, name, industry, country, partner_id FROM accounts ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Client knowledge ─────────────────────────────────────────────────
    def _to_knowledge(self, r: sqlite3.Row) -> KnowledgeEntry:
        raw = r["content"]
        try:
            content = json.loads(raw) if raw else ""
        except (ValueError, TypeError):
            content = raw
        return KnowledgeEntry(
            id=r["id"], account_id=r["account_id"], kind=r["kind"] or "learning",
            title=r["title"] or "", content=content, learned_by=r["learned_by"] or "human",
            created_at=r["created_at"] or "", tags=json.loads(r["tags"] or "[]"),
        )

    def add_knowledge(self, e: KnowledgeEntry) -> KnowledgeEntry:
        content_txt = e.content if isinstance(e.content, str) else json.dumps(e.content)
        searchable = f"{e.title} {content_txt} {' '.join(e.tags)} {e.kind}".lower()
        with self._conn() as c:
            c.execute(
                """INSERT INTO knowledge_entries
                   (id, account_id, kind, title, content, learned_by, created_at, tags, searchable)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (e.id, e.account_id, e.kind, e.title,
                 json.dumps(e.content), e.learned_by, e.created_at,
                 json.dumps(e.tags), searchable),
            )
        return e

    def list_knowledge(self, account_id: str, kind: Optional[str] = None,
                       limit: int = 200) -> list[KnowledgeEntry]:
        q = "SELECT * FROM knowledge_entries WHERE account_id=?"
        args: list = [account_id]
        if kind:
            q += " AND kind=?"
            args.append(kind)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            return [self._to_knowledge(r) for r in c.execute(q, args).fetchall()]

    def search_knowledge(self, account_id: str, query: Optional[str],
                         limit: int = 12) -> list[KnowledgeEntry]:
        """Keyword retrieval (vector search is the future seam). Ranks by how
        many query terms appear in the entry's searchable text."""
        if not query:
            return self.list_knowledge(account_id, limit=limit)
        terms = [t for t in query.lower().split() if len(t) > 2]
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM knowledge_entries WHERE account_id=? ORDER BY created_at DESC",
                (account_id,),
            ).fetchall()
        scored = []
        for r in rows:
            s = r["searchable"] or ""
            hits = sum(1 for t in terms if t in s)
            if hits:
                scored.append((hits, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._to_knowledge(r) for _, r in scored[:limit]]

    # ── Owned dataset: every agent run ───────────────────────────────────
    def log_run(self, d: dict) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO agent_runs
                   (task, model, account_id, engagement_id, system, input, output,
                    raw_text, input_tokens, output_tokens, ms, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (d.get("task"), d.get("model"), d.get("account_id"),
                 d.get("engagement_id"), d.get("system"), d.get("input"),
                 json.dumps(d.get("output")) if d.get("output") is not None else None,
                 d.get("raw_text"), d.get("input_tokens"), d.get("output_tokens"),
                 d.get("ms"), d.get("error"), _ts()),
            )

    def list_runs(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, task, model, account_id, engagement_id, input_tokens, "
                "output_tokens, ms, error, created_at FROM agent_runs "
                "ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
