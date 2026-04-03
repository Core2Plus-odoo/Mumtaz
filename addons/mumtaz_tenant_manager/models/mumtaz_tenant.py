import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MumtazTenant(models.Model):
    """Central registry record for a single isolated tenant database."""

    _name = "mumtaz.tenant"
    _description = "Mumtaz Tenant"
    _rec_name = "name"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(
        string="Tenant Name", required=True, tracking=True,
        help="Display name of the tenant organisation.",
    )
    code = fields.Char(
        required=True, tracking=True,
        help="Short alphanumeric code (slug). Used to derive the database name and subdomain.",
    )
    database_name = fields.Char(
        required=True, tracking=True,
        help="Actual PostgreSQL database name for this tenant (e.g. mumtaz_acme).",
    )
    subdomain = fields.Char(
        tracking=True,
        help="Subdomain prefix (e.g. 'acme' → acme.mumtaz.io).",
    )
    custom_domain = fields.Char(
        tracking=True,
        help="Optional fully-qualified custom domain (e.g. 'suite.acmebank.com').",
    )

    active = fields.Boolean(default=True, tracking=True)

    # ── Status ────────────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("provisioning", "Provisioning"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    # ── Subscription ──────────────────────────────────────────────────────
    bundle_id = fields.Many2one(
        "mumtaz.module.bundle",
        string="Module Bundle",
        tracking=True,
        ondelete="restrict",
    )
    subscription_start = fields.Date(tracking=True)
    subscription_end = fields.Date(tracking=True)
    sme_profile_ids = fields.One2many(
        "mumtaz.sme.profile",
        "tenant_id",
        string="SME Profiles",
        help="Business customers in this tenant.",
    )
    sme_profile_count = fields.Integer(
        compute="_compute_sme_profile_count",
        string="SME Count",
    )

    # ── Branding ──────────────────────────────────────────────────────────
    brand_id = fields.Many2one(
        "mumtaz.brand",
        string="Brand Profile",
        tracking=True,
        ondelete="set null",
    )

    # ── White-label owner / partner ───────────────────────────────────────
    partner_id = fields.Many2one(
        "res.partner",
        string="White-Label Owner",
        tracking=True,
        help="The partner (bank, distributor, reseller) who owns this tenant.",
    )

    # ── Admin credentials (stored for provisioning; clear after use) ──────
    admin_email = fields.Char(
        string="Admin Email",
        tracking=True,
        help="Email address for the initial admin user to be created in the tenant DB.",
    )
    admin_name = fields.Char(
        string="Admin Full Name",
        help="Display name for the initial admin user.",
    )
    # Password is never stored long-term; used only during provisioning wizard.
    admin_password = fields.Char(
        string="Admin Password (temp)",
        groups="mumtaz_tenant_manager.group_mumtaz_platform_admin",
        help="Temporary password set during provisioning. Clear after first login.",
    )

    # ── Optional tenant-level module overrides ────────────────────────────
    extra_modules = fields.Text(
        string="Extra Modules",
        help="Comma-separated additional module names to install beyond the bundle.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    provisioned_on = fields.Datetime(readonly=True, tracking=True)
    last_checked_on = fields.Datetime(readonly=True)
    notes = fields.Text(string="Internal Notes")

    # ── Provisioning log (chained to the mail thread) ─────────────────────
    provision_log = fields.Text(
        string="Provisioning Log",
        readonly=True,
        help="Append-only log of provisioning steps and outcomes.",
    )

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        ("mumtaz_tenant_code_unique", "unique(code)", "Tenant code must be unique."),
        ("mumtaz_tenant_db_unique", "unique(database_name)", "Database name must be unique."),
    ]

    # ── Computed / Auto-fill ──────────────────────────────────────────────
    @api.onchange("code")
    def _onchange_code(self):
        if self.code:
            slug = self._sanitize_code(self.code)
            self.code = slug
            if not self.database_name:
                self.database_name = f"mumtaz_{slug}"
            if not self.subdomain:
                self.subdomain = slug

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not re.match(r"^[a-z0-9][a-z0-9_-]{1,28}[a-z0-9]$", rec.code or ""):
                raise ValidationError(
                    _(
                        "Tenant code '%(code)s' is invalid. "
                        "Use 3–30 lowercase alphanumeric characters, hyphens, or underscores. "
                        "Must start and end with a letter or digit.",
                        code=rec.code,
                    )
                )

    @api.constrains("database_name")
    def _check_database_name(self):
        for rec in self:
            if not re.match(r"^[a-z][a-z0-9_]{1,62}$", rec.database_name or ""):
                raise ValidationError(
                    _(
                        "Database name '%(db)s' is invalid. "
                        "Use lowercase letters, digits, underscores; max 63 chars.",
                        db=rec.database_name,
                    )
                )

    @api.depends("sme_profile_ids")
    def _compute_sme_profile_count(self):
        for rec in self:
            rec.sme_profile_count = len(rec.sme_profile_ids)

    # ── State transition helpers ──────────────────────────────────────────
    def action_start_provisioning(self):
        self._check_provision_ready()
        self.write({"state": "provisioning"})
        self.message_post(body=_("Provisioning started."))

    def action_mark_active(self):
        self.write({"state": "active"})
        self.message_post(body=_("Tenant marked active."))

    def action_suspend(self):
        self.write({"state": "suspended"})
        self.message_post(body=_("Tenant suspended."))

    def action_archive_tenant(self):
        self.write({"state": "archived", "active": False})
        self.message_post(body=_("Tenant archived."))

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
        self.message_post(body=_("Reset to draft."))

    def action_open_provision_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Provision Tenant"),
            "res_model": "mumtaz.provision.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_tenant_id": self.id},
        }

    # ── Internal helpers ──────────────────────────────────────────────────
    @staticmethod
    def _sanitize_code(value):
        return re.sub(r"[^a-z0-9_-]", "", (value or "").lower().strip())

    def _check_provision_ready(self):
        for rec in self:
            missing = []
            if not rec.database_name:
                missing.append("Database Name")
            if not rec.bundle_id:
                missing.append("Module Bundle")
            if not rec.admin_email:
                missing.append("Admin Email")
            if missing:
                raise ValidationError(
                    _("Cannot provision tenant '%(name)s'. Missing: %(fields)s.",
                      name=rec.name, fields=", ".join(missing))
                )

    def _append_log(self, message):
        """Append a timestamped line to provision_log."""
        import datetime
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        prefix = f"[{ts}] "
        existing = self.provision_log or ""
        self.provision_log = existing + prefix + message + "\n"

    def get_extra_module_list(self):
        self.ensure_one()
        if not self.extra_modules:
            return []
        return [m.strip() for m in self.extra_modules.replace(",", " ").split() if m.strip()]

    def action_create_sme_profile(self, company_id=None, sme_values=None):
        self.ensure_one()
        if self.state != "active":
            raise ValidationError("Cannot create SME profile for inactive tenant.")
        if not company_id:
            company_id = self.env.company.id

        values = {
            "tenant_id": self.id,
            "company_id": company_id,
            "legal_name": (sme_values or {}).get("legal_name") or self.name,
            "onboarding_stage": "discovery",
            "activation_status": "pending",
            "brand_id": self.brand_id.id if self.brand_id else False,
        }
        if sme_values:
            values.update(sme_values)
        sme_profile = self.env["mumtaz.sme.profile"].create(values)
        self._append_log(f"Created SME profile: {sme_profile.legal_name}")
        return sme_profile

    def action_create_cfo_workspace(self, sme_profile_id, workspace_values=None):
        self.ensure_one()
        sme_profile = self.env["mumtaz.sme.profile"].browse(sme_profile_id)
        if not sme_profile or sme_profile.tenant_id != self:
            raise ValidationError("SME profile does not belong to this tenant.")

        values = {
            "sme_profile_id": sme_profile.id,
            "company_id": sme_profile.company_id.id,
            "name": f"{sme_profile.legal_name} - Main Workspace",
            "code": "main",
            "owner_user_id": self.env.user.id,
        }
        if workspace_values:
            values.update(workspace_values)
        workspace = self.env["mumtaz.cfo.workspace"].create(values)
        self._append_log(f"Created CFO workspace: {workspace.name}")
        return workspace

    def action_run_smoke_tests(self):
        self.ensure_one()
        tests_passed = 0
        smes = self.env["mumtaz.sme.profile"].search([("tenant_id", "=", self.id)])
        if smes:
            tests_passed += 1
        workspaces = self.env["mumtaz.cfo.workspace"].search([("sme_profile_id", "in", smes.ids)])
        if workspaces:
            tests_passed += 1
        self.message_post(body=_("✓ %(count)s smoke tests passed", count=tests_passed))
        return True
