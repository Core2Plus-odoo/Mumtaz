"""Durable engagement store (SQLite).

This is the API's working state, so engagements survive a restart. Odoo remains
the system of record for business objects (see sync.py); this is the index the
app reads and writes on every request. Point C2P_STORE at a path on the VPS, or
swap the three methods for a Postgres-backed implementation later.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Optional

from models import Engagement

DB_PATH = os.getenv("C2P_STORE", "delivery.db")

_DDL = """
CREATE TABLE IF NOT EXISTS engagements (
  id            TEXT PRIMARY KEY,
  company       TEXT NOT NULL,
  odoo_db       TEXT,
  crm_lead_id   INTEGER,
  sale_order_id INTEGER,
  project_id    INTEGER,
  created_at    TEXT,
  stages        TEXT NOT NULL DEFAULT '{}'
);
"""


class EngagementStore:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        with self._conn() as c:
            c.executescript(_DDL)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _to_eng(self, r: sqlite3.Row) -> Engagement:
        return Engagement(
            id=r["id"], company=r["company"], odoo_db=r["odoo_db"],
            crm_lead_id=r["crm_lead_id"], sale_order_id=r["sale_order_id"],
            project_id=r["project_id"], created_at=r["created_at"] or "",
            stages=json.loads(r["stages"] or "{}"),
        )

    def create(self, company: str, odoo_db: Optional[str]) -> Engagement:
        eng = Engagement(company=company, odoo_db=odoo_db)
        self.save(eng)
        return eng

    def save(self, eng: Engagement) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO engagements
                   (id, company, odoo_db, crm_lead_id, sale_order_id, project_id, created_at, stages)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     company=excluded.company, odoo_db=excluded.odoo_db,
                     crm_lead_id=excluded.crm_lead_id, sale_order_id=excluded.sale_order_id,
                     project_id=excluded.project_id, stages=excluded.stages""",
                (eng.id, eng.company, eng.odoo_db, eng.crm_lead_id, eng.sale_order_id,
                 eng.project_id, eng.created_at, json.dumps(eng.stages)),
            )

    def get(self, eng_id: str) -> Optional[Engagement]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM engagements WHERE id=?", (eng_id,)).fetchone()
            return self._to_eng(r) if r else None

    def list(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, company, stages FROM engagements ORDER BY created_at DESC"
            ).fetchall()
            return [
                {"id": r["id"], "company": r["company"],
                 "stages": list(json.loads(r["stages"] or "{}"))}
                for r in rows
            ]
