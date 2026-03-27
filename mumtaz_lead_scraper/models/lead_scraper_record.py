from odoo import _, fields, models


class LeadScraperRecord(models.Model):
    """Stores a single extracted lead record before/after CRM insertion."""

    _name = "lead.scraper.record"
    _description = "Lead Scraper Extracted Record"
    _rec_name = "company_name"
    _order = "id desc"

    job_id = fields.Many2one(
        "lead.scraper.job", required=True, ondelete="cascade", index=True
    )
    source_id = fields.Many2one(
        "lead.scraper.source", required=True, ondelete="cascade", index=True
    )

    # ── Extracted lead data ───────────────────────────────────────────────
    company_name = fields.Char(string="Company")
    contact_name = fields.Char(string="Contact")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    website = fields.Char(string="Website")
    city = fields.Char(string="City")
    country_name = fields.Char(string="Country")
    industry = fields.Char(string="Industry")
    source_url = fields.Char(string="Source Page URL")
    description = fields.Text(string="Notes / Description")
    raw_payload = fields.Text(string="Raw Extracted Data (JSON)")

    # ── Normalization ─────────────────────────────────────────────────────
    normalized_status = fields.Selection(
        [
            ("raw", "Raw"),
            ("normalized", "Normalized"),
            ("failed", "Failed"),
        ],
        default="raw",
        string="Normalization",
    )

    # ── Deduplication ─────────────────────────────────────────────────────
    duplicate_status = fields.Selection(
        [
            ("unchecked", "Not Checked"),
            ("unique", "Unique"),
            ("duplicate", "Duplicate"),
        ],
        default="unchecked",
        string="Duplicate Check",
    )
    duplicate_lead_id = fields.Many2one(
        "crm.lead",
        string="Existing Lead (Duplicate)",
        help="The existing CRM lead this record duplicates.",
        readonly=True,
    )

    # ── Processing ────────────────────────────────────────────────────────
    processing_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("normalized", "Normalized"),
            ("crm_created", "CRM Lead Created"),
            ("skipped", "Skipped"),
            ("failed", "Failed"),
        ],
        default="pending",
        string="Status",
    )
    crm_lead_id = fields.Many2one("crm.lead", string="CRM Lead", readonly=True)
    processing_notes = fields.Text(string="Processing Notes", readonly=True)

    # ── Actions ───────────────────────────────────────────────────────────
    def action_push_to_crm(self):
        self.ensure_one()
        if self.processing_status == "crm_created":
            return
        from ..services.crm_mapper import CRMMapper
        CRMMapper(self.env).create_lead(self)

    def action_check_duplicate(self):
        from ..services.deduplicator import Deduplicator
        dedup = Deduplicator(self.env)
        for rec in self:
            dedup.check(rec)

    def action_mark_skipped(self):
        self.write({"processing_status": "skipped"})

    def action_open_crm_lead(self):
        self.ensure_one()
        if not self.crm_lead_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": _("CRM Lead"),
            "res_model": "crm.lead",
            "res_id": self.crm_lead_id.id,
            "view_mode": "form",
        }
