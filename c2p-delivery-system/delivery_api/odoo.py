"""Odoo XML-RPC bridge.

Read side (introspection): list installed modules and the real schema so the
functional and developer agents reason against the actual tenant instead of
guessing. Write side: create the CRM lead, quotation and project that make Odoo
the system of record for the engagement.

Multi-tenant note: Mumtaz runs one database per tenant, so every call takes a
`db`. Auth is per (db, user, password); credentials come from environment.
"""

from __future__ import annotations

import base64
import json
import os
import xmlrpc.client
from functools import lru_cache
from typing import Any, Optional

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")


class OdooClient:
    def __init__(self, db: str, url: str = ODOO_URL,
                 user: str = ODOO_USER, password: str = ODOO_PASSWORD):
        self.db = db
        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        self._uid: Optional[int] = None

    @property
    def uid(self) -> int:
        if self._uid is None:
            self._uid = self._common.authenticate(self.db, self.user, self.password, {})
            if not self._uid:
                raise PermissionError(f"Odoo auth failed for db '{self.db}' as '{self.user}'")
        return self._uid

    def execute(self, model: str, method: str, *args, **kw) -> Any:
        return self._models.execute_kw(
            self.db, self.uid, self.password, model, method, list(args), kw
        )

    # ---- read side: introspection -------------------------------------------
    def installed_modules(self) -> list[str]:
        recs = self.execute(
            "ir.module.module", "search_read",
            [("state", "=", "installed")], fields=["name"],
        )
        return sorted(r["name"] for r in recs)

    def models_list(self) -> list[dict]:
        return self.execute("ir.model", "search_read", [], fields=["model", "name"])

    def fields_of(self, model: str) -> list[dict]:
        return self.execute(
            "ir.model.fields", "search_read",
            [("model", "=", model)], fields=["name", "field_description", "ttype", "required"],
        )

    # ---- write side: system of record ---------------------------------------
    def create_lead(self, name: str, partner_name: str,
                    description: str = "", **vals) -> int:
        payload = {"name": name, "partner_name": partner_name,
                   "description": description, "type": "opportunity", **vals}
        return self.execute("crm.lead", "create", payload)

    def create_quotation(self, partner_id: int, note: str = "", **vals) -> int:
        payload = {"partner_id": partner_id, "note": note, **vals}
        return self.execute("sale.order", "create", payload)

    def create_project(self, name: str, **vals) -> int:
        return self.execute("project.project", "create", {"name": name, **vals})

    def create_task(self, project_id: int, name: str, **vals) -> int:
        return self.execute(
            "project.task", "create", {"project_id": project_id, "name": name, **vals}
        )

    def partner_of_lead(self, lead_id: int) -> Optional[int]:
        """Return the lead's linked partner id, creating a company partner from
        the lead's name if none is linked yet (needed to raise a quotation)."""
        rec = self.execute("crm.lead", "read", [lead_id], fields=["partner_id", "partner_name"])
        if not rec:
            return None
        if rec[0].get("partner_id"):
            return rec[0]["partner_id"][0]
        name = rec[0].get("partner_name") or "Customer"
        return self.execute("res.partner", "create", {"name": name, "is_company": True})

    def message_post(self, res_model: str, res_id: int, body: str) -> Any:
        """Log a note to a record's chatter (canonical comms log in Odoo)."""
        return self.execute(res_model, "message_post", [res_id], body=body)

    def attach_json(self, res_model: str, res_id: int, name: str, obj: Any) -> int:
        """Upsert a JSON attachment on a record (deletes a same-named one first
        so re-running a stage replaces rather than piles up)."""
        existing = self.execute(
            "ir.attachment", "search",
            [("res_model", "=", res_model), ("res_id", "=", res_id), ("name", "=", name)],
        )
        if existing:
            self.execute("ir.attachment", "unlink", existing)
        data = base64.b64encode(json.dumps(obj, indent=2).encode()).decode()
        return self.execute("ir.attachment", "create", {
            "name": name, "res_model": res_model, "res_id": res_id,
            "datas": data, "mimetype": "application/json",
        })


@lru_cache(maxsize=16)
def get_client(db: str) -> OdooClient:
    """Cached client per tenant DB. Cache is keyed by db only; credentials come
    from the environment, so this is safe for a single operator (C2P) context."""
    return OdooClient(db)
