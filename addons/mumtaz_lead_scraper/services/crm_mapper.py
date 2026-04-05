"""
CRM Mapper
==========
Maps a lead.scraper.record to a crm.lead and creates it.
"""

import logging

_logger = logging.getLogger(__name__)


class CRMMapper:
    """Creates CRM leads from normalized scraper records."""

    def __init__(self, env):
        self.env = env

    def create_lead(self, record):
        """
        Create a crm.lead from record.
        Updates record.crm_lead_id and record.processing_status on success.
        """
        if record.processing_status == "crm_created":
            _logger.debug("Record %s already in CRM — skipped", record.id)
            return

        if record.duplicate_status == "duplicate":
            record.write(
                {
                    "processing_status": "skipped",
                    "processing_notes": (record.processing_notes or "")
                    + " | Skipped: duplicate",
                }
            )
            return

        source = record.source_id
        vals = self._build_vals(record, source)

        try:
            lead = self.env["crm.lead"].create(vals)
            record.write(
                {
                    "crm_lead_id": lead.id,
                    "processing_status": "crm_created",
                    "processing_notes": f"CRM lead {lead.id} created.",
                }
            )
            _logger.info("CRM lead %s created from scraper record %s", lead.id, record.id)
        except Exception as exc:
            _logger.exception("CRM lead creation failed for record %s", record.id)
            record.write(
                {
                    "processing_status": "failed",
                    "processing_notes": f"CRM creation error: {exc}",
                }
            )

    # ── Mapping helpers ───────────────────────────────────────────────────

    def _build_vals(self, record, source):
        vals = {
            "name": self._lead_name(record),
            "partner_name": record.company_name or record.contact_name or "Unknown Lead",
            "contact_name": record.contact_name or "",
            "email_from": record.email or "",
            "phone": record.phone or "",
            "website": record.website or "",
            "city": record.city or "",
            "description": self._description(record),
        }

        # Country lookup
        if record.country_name:
            country = self.env["res.country"].search(
                [("name", "=ilike", record.country_name)], limit=1
            )
            if country:
                vals["country_id"] = country.id

        # CRM team / salesperson from source config
        if source.crm_team_id:
            vals["team_id"] = source.crm_team_id.id
        if source.user_id:
            vals["user_id"] = source.user_id.id

        return vals

    def _lead_name(self, record):
        parts = []
        if record.company_name:
            parts.append(record.company_name)
        elif record.contact_name:
            parts.append(record.contact_name)
        else:
            parts.append("Lead")
        if record.source_id:
            parts.append(f"(via {record.source_id.name})")
        return " ".join(parts)

    def _description(self, record):
        lines = [
            f"Scraped from: {record.source_id.name}",
            f"Source URL: {record.source_url or '—'}",
        ]
        if record.industry:
            lines.append(f"Industry: {record.industry}")
        if record.city:
            lines.append(f"City: {record.city}")
        if record.country_name:
            lines.append(f"Country: {record.country_name}")
        if record.description:
            lines.append(f"\n{record.description}")
        return "\n".join(lines)
