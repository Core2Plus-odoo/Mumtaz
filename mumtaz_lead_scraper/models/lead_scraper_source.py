import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LeadScraperSource(models.Model):
    """Defines a website or API source to scrape for leads."""

    _name = "lead.scraper.source"
    _description = "Lead Scraper Source"
    _rec_name = "name"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(required=True, tracking=True)
    url = fields.Char(string="Source URL", required=True, tracking=True)
    source_type = fields.Selection(
        [
            ("html", "HTML Page"),
            ("listing", "Listing + Detail Pages"),
            ("api", "API / JSON Endpoint"),
            ("sitemap", "Sitemap"),
            ("ptp", "Pakistan Trade Portal"),
        ],
        default="html",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text()

    # ── Parsing ───────────────────────────────────────────────────────────
    parsing_mode = fields.Selection(
        [
            ("auto", "Auto-detect (Heuristic)"),
            ("css", "CSS Selectors"),
            ("json", "JSON Path"),
        ],
        default="auto",
        required=True,
        tracking=True,
    )
    selector_config = fields.Text(
        string="Selector / Path Config (JSON)",
        help=(
            "JSON configuration for CSS selectors or JSON paths.\n\n"
            "CSS example:\n"
            '{"container": ".listing-item", "company_name": ".name", '
            '"email": ".email", "phone": ".phone", "website": "a.site@href"}\n\n'
            "JSON API example:\n"
            '{"root_path": "data.results", "company_name": "name", '
            '"email": "contact.email", "phone": "contact.phone"}'
        ),
    )

    # ── Request settings ──────────────────────────────────────────────────
    request_delay = fields.Float(
        string="Delay Between Requests (s)",
        default=2.0,
        help="Seconds to wait between HTTP requests. Minimum 1.0 recommended.",
    )
    max_pages = fields.Integer(
        string="Max Pages Per Run",
        default=5,
        help="Safety cap on pages fetched per run. 0 = unlimited (use with caution).",
    )
    respect_robots = fields.Boolean(
        string="Respect robots.txt",
        default=True,
        help="Skip pages disallowed by the site's robots.txt.",
    )

    # ── CRM defaults ──────────────────────────────────────────────────────
    crm_team_id = fields.Many2one("crm.team", string="Default Sales Team", tracking=True)
    user_id = fields.Many2one("res.users", string="Default Salesperson", tracking=True)

    # ── Scheduling ────────────────────────────────────────────────────────
    auto_schedule = fields.Boolean(string="Enable Scheduled Scraping", default=False, tracking=True)
    schedule_interval = fields.Selection(
        [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        default="weekly",
    )
    auto_push_crm = fields.Boolean(
        string="Auto-Push to CRM",
        default=False,
        help="Automatically create CRM leads for unique records after each run.",
        tracking=True,
    )
    last_run_date = fields.Datetime(readonly=True, tracking=True)

    # ── Stats ─────────────────────────────────────────────────────────────
    job_count = fields.Integer(compute="_compute_stats", string="Runs")
    total_leads_created = fields.Integer(compute="_compute_stats", string="CRM Leads Created")

    def _compute_stats(self):
        Job = self.env["lead.scraper.job"]
        Record = self.env["lead.scraper.record"]
        for rec in self:
            rec.job_count = Job.search_count([("source_id", "=", rec.id)])
            rec.total_leads_created = Record.search_count(
                [("source_id", "=", rec.id), ("processing_status", "=", "crm_created")]
            )

    # ── Actions ───────────────────────────────────────────────────────────
    def action_run_scraper(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Run Scraper"),
            "res_model": "lead.scraper.run.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_source_id": self.id},
        }

    def action_view_jobs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scraping Jobs"),
            "res_model": "lead.scraper.job",
            "view_mode": "list,form",
            "domain": [("source_id", "=", self.id)],
        }

    def action_view_records(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Extracted Leads"),
            "res_model": "lead.scraper.record",
            "view_mode": "list,form",
            "domain": [("source_id", "=", self.id)],
        }

    # ── Scheduled run (called by cron) ────────────────────────────────────
    def action_scheduled_run(self):
        """Entry point for the cron job. Runs all active scheduled sources."""
        sources = self.search([("active", "=", True), ("auto_schedule", "=", True)])
        for source in sources:
            try:
                from ..services.engine import ScraperEngine
                engine = ScraperEngine(self.env)
                engine.run(source, auto_push_crm=source.auto_push_crm, triggered_by="cron")
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Scheduled scrape failed for source %s", source.name
                )

    # ── Helpers ───────────────────────────────────────────────────────────
    def get_selector_config(self):
        self.ensure_one()
        if not self.selector_config:
            return {}
        try:
            return json.loads(self.selector_config)
        except (json.JSONDecodeError, TypeError):
            return {}

    _sql_constraints = [
        ("lead_scraper_source_name_unique", "unique(name)", "Source name must be unique."),
    ]
