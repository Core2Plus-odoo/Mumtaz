import datetime

from odoo import _, api, fields, models


class LeadScraperJob(models.Model):
    """Tracks a single scraping run against a source."""

    _name = "lead.scraper.job"
    _description = "Lead Scraper Job"
    _rec_name = "name"
    _order = "start_time desc"
    _inherit = ["mail.thread"]

    name = fields.Char(compute="_compute_name", store=True)
    source_id = fields.Many2one(
        "lead.scraper.source", required=True, ondelete="cascade", tracking=True
    )

    # ── Timing ────────────────────────────────────────────────────────────
    start_time = fields.Datetime(readonly=True)
    end_time = fields.Datetime(readonly=True)
    duration = fields.Float(
        compute="_compute_duration", string="Duration (s)", store=True
    )

    # ── Status ────────────────────────────────────────────────────────────
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )
    triggered_by = fields.Selection(
        [("manual", "Manual"), ("cron", "Scheduled")], default="manual"
    )

    # ── Counters ──────────────────────────────────────────────────────────
    total_found = fields.Integer(default=0, string="Found")
    total_processed = fields.Integer(default=0, string="Processed")
    total_created = fields.Integer(default=0, string="CRM Created")
    total_duplicates = fields.Integer(default=0, string="Duplicates")
    total_skipped = fields.Integer(default=0, string="Skipped")
    total_failed = fields.Integer(default=0, string="Failed")

    # ── Logs ──────────────────────────────────────────────────────────────
    log_text = fields.Text(string="Run Log", readonly=True)
    error_message = fields.Text(readonly=True)

    # ── Records ───────────────────────────────────────────────────────────
    record_ids = fields.One2many("lead.scraper.record", "job_id", string="Extracted Records")
    record_count = fields.Integer(compute="_compute_record_count", string="Records")

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends("source_id", "start_time")
    def _compute_name(self):
        for rec in self:
            ts = rec.start_time.strftime("%Y-%m-%d %H:%M") if rec.start_time else "Pending"
            rec.name = f"{rec.source_id.name} — {ts}" if rec.source_id else ts

    @api.depends("start_time", "end_time")
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                rec.duration = (rec.end_time - rec.start_time).total_seconds()
            else:
                rec.duration = 0.0

    def _compute_record_count(self):
        for rec in self:
            rec.record_count = len(rec.record_ids)

    # ── Helpers ───────────────────────────────────────────────────────────
    def append_log(self, message):
        ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
        safe_message = str(message or "").replace("\x00", "")
        self.log_text = (self.log_text or "").replace("\x00", "") + f"[{ts}] {safe_message}\n"

    # ── Actions ───────────────────────────────────────────────────────────
    def action_view_records(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Extracted Records"),
            "res_model": "lead.scraper.record",
            "view_mode": "list,form",
            "domain": [("job_id", "=", self.id)],
        }

    def action_push_all_to_crm(self):
        """Push all normalized unique records from this job to CRM."""
        self.ensure_one()
        from ..services.crm_mapper import CRMMapper
        from ..services.deduplicator import Deduplicator

        mapper = CRMMapper(self.env)
        deduplicator = Deduplicator(self.env)
        created_before = len(
            self.record_ids.filtered(lambda r: r.processing_status == "crm_created")
        )
        candidates = self.record_ids.filtered(
            lambda r: r.processing_status == "normalized"
        )
        created_attempts = 0

        for record in candidates:
            if record.duplicate_status == "unchecked":
                deduplicator.check(record)
            if record.duplicate_status == "unique":
                mapper.create_lead(record)
                created_attempts += 1

        created = self.record_ids.filtered(
            lambda r: r.processing_status == "crm_created"
        )
        created_now = max(len(created) - created_before, 0)
        self.total_created = len(created)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("CRM Push Complete"),
                "message": _(
                    "%(created)s leads pushed to CRM (%(attempted)s attempted).",
                    created=created_now,
                    attempted=created_attempts,
                ),
                "type": "success",
            },
        }

    def action_cancel(self):
        self.write({"status": "cancelled"})
