from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LeadScraperRunWizard(models.TransientModel):
    """Step-through wizard to run a scraping job with live result summary."""

    _name = "lead.scraper.run.wizard"
    _description = "Run Lead Scraper Wizard"

    source_id = fields.Many2one("lead.scraper.source", required=True, readonly=True)
    source_name = fields.Char(related="source_id.name", readonly=True)
    source_url = fields.Char(related="source_id.url", readonly=True)
    parsing_mode = fields.Selection(related="source_id.parsing_mode", readonly=True)

    auto_push_crm = fields.Boolean(
        string="Auto Push to CRM",
        default=False,
        help="Automatically create CRM leads for all unique extracted records.",
    )

    state = fields.Selection(
        [("confirm", "Confirm"), ("done", "Done")],
        default="confirm",
        readonly=True,
    )

    result_job_id = fields.Many2one("lead.scraper.job", readonly=True)
    result_status = fields.Char(readonly=True)
    result_summary = fields.Text(string="Run Summary", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        sanitized = [self._sanitize_nul_strings(vals) for vals in vals_list]
        return super().create(sanitized)

    def write(self, vals):
        return super().write(self._sanitize_nul_strings(vals))

    @staticmethod
    def _sanitize_nul_strings(vals):
        clean = {}
        for key, value in (vals or {}).items():
            if isinstance(value, str):
                clean[key] = value.replace("\x00", "")
            else:
                clean[key] = value
        return clean

    def action_run(self):
        self.ensure_one()
        from ..services.engine import ScraperEngine

        engine = ScraperEngine(self.env)
        job = engine.run(
            self.source_id,
            auto_push_crm=self.auto_push_crm,
            triggered_by="manual",
        )
        self._sanitize_records_for_nul(job)

        summary = (
            f"Status       : {job.status.upper()}\n"
            f"Records found: {job.total_found}\n"
            f"Processed    : {job.total_processed}\n"
            f"CRM created  : {job.total_created}\n"
            f"Duplicates   : {job.total_duplicates}\n"
            f"Skipped      : {job.total_skipped}\n"
            f"Failed       : {job.total_failed}\n"
        )

        self.write(
            {
                "state": "done",
                "result_job_id": job.id,
                "result_status": job.status,
                "result_summary": summary,
            }
        )
        try:
            self.env.flush_all()
        except ValueError as exc:
            msg = str(exc or "").replace("\x00", "")
            raise UserError(
                _("Scraper run created invalid text payloads. Please retry. Details: %s") % msg
            ) from exc

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_job(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scraping Job"),
            "res_model": "lead.scraper.job",
            "res_id": self.result_job_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_close(self):
        return {"type": "ir.actions.act_window_close"}

    def _sanitize_records_for_nul(self, job):
        targets = self.env["lead.scraper.run.wizard"].browse(self.id)
        if job:
            targets |= job
            targets |= job.source_id
            targets |= job.record_ids

        for rec in targets:
            vals = {}
            for field_name, field in rec._fields.items():
                if field.type not in ("char", "text", "html"):
                    continue
                value = rec[field_name]
                if isinstance(value, str) and "\x00" in value:
                    vals[field_name] = value.replace("\x00", "")
            if vals:
                rec.write(vals)
