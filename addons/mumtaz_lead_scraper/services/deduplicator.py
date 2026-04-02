"""
Deduplicator
============
Checks scraped records against existing crm.lead records
using a priority cascade of matching rules.
"""

import logging
import re

_logger = logging.getLogger(__name__)


class Deduplicator:
    """
    Duplicate detection using cascading rules:
    1. Email match (strongest)
    2. Phone match (normalized digits)
    3. Company name + website
    4. Company name only (weakest / advisory)
    """

    def __init__(self, env):
        self.env = env

    def check(self, record):
        """
        Check record against existing CRM leads.
        Writes duplicate_status, duplicate_lead_id, and processing_status.
        """
        existing, reason = self._find_duplicate(record)

        if existing:
            record.write(
                {
                    "duplicate_status": "duplicate",
                    "duplicate_lead_id": existing.id,
                    "processing_status": "skipped",
                    "processing_notes": f"Duplicate: {reason}",
                }
            )
            _logger.info(
                "Duplicate found for scraper record %s → CRM lead %s (%s)",
                record.id,
                existing.id,
                reason,
            )
        else:
            record.write({"duplicate_status": "unique"})

    def _find_duplicate(self, record):
        Lead = self.env["crm.lead"]

        # 1. Email
        if record.email:
            lead = Lead.search(
                [("email_from", "=ilike", record.email), ("active", "in", [True, False])],
                limit=1,
            )
            if lead:
                return lead, f"email match ({record.email})"

        # 2. Phone (compare normalised digit strings)
        if record.phone:
            digits = re.sub(r"\D", "", record.phone)
            if len(digits) >= 7:
                # Search last 8 digits to handle country code variations
                tail = digits[-8:]
                all_leads = Lead.search(
                    [("phone", "!=", False), ("active", "in", [True, False])],
                    limit=500,
                )
                for lead in all_leads:
                    lead_digits = re.sub(r"\D", "", lead.phone or "")
                    if len(lead_digits) >= 7 and lead_digits[-8:] == tail:
                        return lead, f"phone match ({record.phone})"

        # 3. Company name + website
        if record.company_name and record.website:
            lead = Lead.search(
                [
                    ("partner_name", "=ilike", record.company_name),
                    ("website", "=ilike", record.website),
                    ("active", "in", [True, False]),
                ],
                limit=1,
            )
            if lead:
                return lead, f"company + website match ({record.company_name})"

        # 4. Company name only (weak — only if very specific)
        if record.company_name and len(record.company_name) > 6:
            lead = Lead.search(
                [
                    ("partner_name", "=ilike", record.company_name),
                    ("active", "in", [True, False]),
                ],
                limit=1,
            )
            if lead:
                return lead, f"company name match ({record.company_name})"

        return None, ""
