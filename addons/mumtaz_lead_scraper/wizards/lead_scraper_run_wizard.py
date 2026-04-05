from odoo import _, fields, models


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

    def action_run(self):
        self.ensure_one()
        from ..services.engine import ScraperEngine

        engine = ScraperEngine(self.env)
        job = engine.run(
            self.source_id,
            auto_push_crm=self.auto_push_crm,
            triggered_by="manual",
        )

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
