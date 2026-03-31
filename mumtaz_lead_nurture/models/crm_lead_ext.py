import datetime
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

NURTURE_STAGES = [
    ("new", "New"),
    ("enrolled", "Enrolled"),
    ("contacted", "Contacted"),
    ("nurturing", "Nurturing"),
    ("responded", "Responded"),
    ("qualified", "Qualified"),
    ("converted", "Converted"),
    ("dead", "Dead"),
]

RESPONSE_STATUSES = [
    ("no_response", "No Response"),
    ("bounced", "Bounced"),
    ("opened", "Opened"),
    ("replied", "Replied"),
    ("interested", "Interested"),
    ("not_interested", "Not Interested"),
    ("demo_requested", "Demo Requested"),
    ("requirement_shared", "Requirement Shared"),
]

INDUSTRY_CLUSTERS = [
    ("textiles", "Textiles / Garments"),
    ("manufacturing", "Manufacturing"),
    ("trading", "Trading / Distribution"),
    ("services", "Services"),
    ("retail", "Retail"),
    ("construction", "Construction"),
    ("food_beverage", "Food & Beverage"),
    ("pharma", "Pharma / Healthcare"),
    ("logistics", "Logistics / Transport"),
    ("it", "IT / Tech"),
    ("other", "Other"),
]


class CrmLeadExt(models.Model):
    _inherit = "crm.lead"

    # ── Source linkage ──────────────────────────────────────────────────
    scraped_source_id = fields.Many2one(
        "lead.scraper.source",
        string="Scraper Source",
        ondelete="set null",
    )

    # ── Segmentation ────────────────────────────────────────────────────
    industry_cluster = fields.Selection(
        INDUSTRY_CLUSTERS, string="Industry Cluster", tracking=True
    )
    company_segment = fields.Selection(
        [
            ("micro", "Micro (1–10)"),
            ("sme", "SME (11–100)"),
            ("mid", "Mid-Market (101–500)"),
            ("enterprise", "Enterprise (500+)"),
        ],
        string="Company Segment",
        tracking=True,
    )
    probable_erp_need_ids = fields.Many2many(
        "lead.nurture.erp.need",
        "crm_lead_erp_need_rel",
        "lead_id",
        "need_id",
        string="Probable ERP Needs",
    )
    use_case_type = fields.Selection(
        [
            ("inventory", "Inventory Management"),
            ("accounting", "Accounting / Finance"),
            ("hrm", "HR & Payroll"),
            ("sales_crm", "Sales / CRM"),
            ("purchase", "Purchase Management"),
            ("manufacturing", "Manufacturing (MRP)"),
            ("ecommerce", "eCommerce Integration"),
            ("full_erp", "Full ERP Replacement"),
            ("other", "Other"),
        ],
        string="Primary Use Case",
    )

    # ── Scoring ─────────────────────────────────────────────────────────
    lead_score = fields.Integer(
        default=0,
        tracking=True,
        help="Initial quality score based on data richness and source quality.",
    )
    qualification_score = fields.Integer(
        default=0,
        tracking=True,
        help="Accumulated nurture score from campaign interactions.",
    )

    # ── Campaign / Sequence ──────────────────────────────────────────────
    nurture_campaign_id = fields.Many2one(
        "lead.nurture.campaign",
        string="Nurture Campaign",
        tracking=True,
        ondelete="set null",
    )
    nurture_sequence_step = fields.Integer(
        string="Current Step",
        default=0,
        help="Last executed step number. 0 = enrolled but not yet started.",
    )
    nurture_stage = fields.Selection(
        NURTURE_STAGES,
        default="new",
        tracking=True,
        string="Nurture Stage",
    )

    # ── Outreach ─────────────────────────────────────────────────────────
    outreach_channel_pref = fields.Selection(
        [
            ("email", "Email"),
            ("whatsapp", "WhatsApp"),
            ("both", "Email + WhatsApp"),
        ],
        string="Outreach Channel",
        default="email",
    )
    response_status = fields.Selection(
        RESPONSE_STATUSES,
        string="Response Status",
        default="no_response",
        tracking=True,
    )
    last_outreach_date = fields.Datetime(string="Last Outreach", readonly=True)
    next_followup_date = fields.Date(string="Next Follow-up", tracking=True)

    # ── Communication Log ─────────────────────────────────────────────────
    nurture_log_ids = fields.One2many(
        "lead.nurture.log", "lead_id", string="Communication History"
    )
    nurture_log_count = fields.Integer(compute="_compute_nurture_log_count", string="Outreach")

    # ── Conversion ────────────────────────────────────────────────────────
    auto_convert_ready = fields.Boolean(
        string="Auto-Convert Ready",
        tracking=True,
        help="Set automatically when qualification score reaches the campaign threshold.",
    )

    # ── Computed helpers ─────────────────────────────────────────────────
    @api.depends("nurture_log_ids")
    def _compute_nurture_log_count(self):
        for rec in self:
            rec.nurture_log_count = len(rec.nurture_log_ids)

    # ── Actions ───────────────────────────────────────────────────────────
    def action_view_nurture_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Communication History"),
            "res_model": "lead.nurture.log",
            "view_mode": "list,form",
            "domain": [("lead_id", "=", self.id)],
            "context": {"default_lead_id": self.id},
        }

    def action_enroll_in_campaign(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Enroll in Campaign"),
            "res_model": "lead.nurture.enroll.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_lead_ids": [(4, r.id) for r in self]},
        }

    def action_qualify_lead(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Qualify Lead"),
            "res_model": "lead.nurture.qualify.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_lead_id": self.id},
        }

    def action_mark_interested(self):
        for lead in self:
            lead._apply_nurture_event("positive_reply")
            lead.write({"response_status": "interested", "nurture_stage": "responded"})

    def action_mark_demo_requested(self):
        for lead in self:
            lead._apply_nurture_event("demo_requested")
            lead.write({"response_status": "demo_requested", "nurture_stage": "responded"})

    def action_mark_not_interested(self):
        for lead in self:
            lead._apply_nurture_event("not_interested")
            lead.write({"response_status": "not_interested", "nurture_stage": "dead"})

    def action_convert_qualified(self):
        """Manually trigger opportunity conversion for qualified leads."""
        from ..services.conversion_engine import ConversionEngine
        engine = ConversionEngine(self.env)
        for lead in self.filtered(lambda l: l.type == "lead"):
            engine.convert(lead)

    # ── Scheduled auto-convert ───────────────────────────────────────────
    def action_run_auto_conversion(self):
        """Called by cron. Converts all auto-convert-ready leads."""
        from ..services.conversion_engine import ConversionEngine
        engine = ConversionEngine(self.env)
        leads = self.search([
            ("auto_convert_ready", "=", True),
            ("type", "=", "lead"),
            ("nurture_stage", "not in", ["converted", "dead"]),
        ])
        for lead in leads:
            try:
                engine.convert(lead)
            except Exception:
                _logger.exception("Auto-convert failed for lead %s", lead.id)

    # ── Sequence scheduler entry ─────────────────────────────────────────
    def action_run_nurture_sequences(self):
        """Called by cron. Advances all leads that are due for next step."""
        from ..services.sequence_runner import SequenceRunner
        runner = SequenceRunner(self.env)
        today = fields.Date.today()
        leads = self.search([
            ("nurture_campaign_id", "!=", False),
            ("nurture_stage", "not in", ["converted", "dead"]),
            ("type", "=", "lead"),
            ("next_followup_date", "<=", today),
        ])
        for lead in leads:
            try:
                runner.advance(lead)
            except Exception:
                _logger.exception("Sequence runner failed for lead %s", lead.id)

    # ── Internal helper ──────────────────────────────────────────────────
    def _apply_nurture_event(self, event_name):
        """Apply a scoring event to this lead. Returns score delta."""
        from ..services.scoring_engine import ScoringEngine
        engine = ScoringEngine(self.env)
        return engine.apply_event(self, event_name)
