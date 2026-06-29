"""Odoo write-back: make Odoo the system of record, one stage at a time.

Best-effort and idempotent. Each stage pushes its business object into Odoo's
native pipeline (crm.lead -> sale.order -> project.project + tasks) and attaches
its JSON deliverable to the right record. The created ids are stored on the
engagement so a re-run updates rather than duplicates. Any Odoo failure is logged
and swallowed — it never blocks the agent or the API response.
"""

from __future__ import annotations

import json
import logging

from models import Engagement
from odoo import get_client

log = logging.getLogger("c2p.sync")


def writeback(eng: Engagement, stage: str, output: dict) -> None:
    if not eng.odoo_db:
        return
    try:
        c = get_client(eng.odoo_db)
    except Exception as exc:
        log.warning("Odoo unavailable for db '%s': %s", eng.odoo_db, exc)
        return

    try:
        if stage == "presales":
            if not eng.crm_lead_id:
                eng.crm_lead_id = c.create_lead(
                    name=f"{eng.company} — {output.get('recommendation', 'opportunity')}",
                    partner_name=eng.company,
                    description=json.dumps(output.get("discovery", {}), indent=2),
                )
            c.attach_json("crm.lead", eng.crm_lead_id, "presales.json", output)

        elif stage == "proposal" and eng.crm_lead_id:
            if not eng.sale_order_id:
                partner_id = c.partner_of_lead(eng.crm_lead_id)
                if partner_id:
                    eng.sale_order_id = c.create_quotation(
                        partner_id, note=output.get("solution_summary", "")
                    )
            model, rid = (("sale.order", eng.sale_order_id)
                          if eng.sale_order_id else ("crm.lead", eng.crm_lead_id))
            c.attach_json(model, rid, "proposal.json", output)

        elif stage == "project":
            if not eng.project_id:
                eng.project_id = c.create_project(output.get("project_name", eng.company))
                for phase in output.get("phases", []):
                    for task in phase.get("tasks", []):
                        c.create_task(eng.project_id, task.get("name", "Task"))
            c.attach_json("project.project", eng.project_id, "project_plan.json", output)

        elif stage in ("functional", "developer") and eng.crm_lead_id:
            c.attach_json("crm.lead", eng.crm_lead_id, f"{stage}.json", output)

    except Exception as exc:
        log.warning("Write-back failed at stage '%s': %s", stage, exc)
