from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.provisioning import ProvisioningDisabled, get_provisioner


class MumtazProvisionWizard(models.TransientModel):
    """
    Step-through wizard for provisioning a new tenant database.

    Opens from the tenant form (button: "Provision Tenant") and walks the
    operator through:
      1. Reviewing / confirming tenant config.
      2. Executing the provisioning sequence (dry-run by default).
      3. Displaying the result log.
    """

    _name = "mumtaz.provision.wizard"
    _description = "Mumtaz Tenant Provisioning Wizard"

    tenant_id = fields.Many2one(
        "mumtaz.tenant",
        string="Tenant",
        required=True,
        readonly=True,
    )

    # Read-only mirrors for confirmation screen
    tenant_name = fields.Char(related="tenant_id.name", readonly=True)
    database_name = fields.Char(related="tenant_id.database_name", readonly=True)
    subdomain = fields.Char(related="tenant_id.subdomain", readonly=True)
    bundle_id = fields.Many2one(related="tenant_id.bundle_id", readonly=True)
    admin_email = fields.Char(related="tenant_id.admin_email", readonly=True)
    brand_id = fields.Many2one(related="tenant_id.brand_id", readonly=True)

    # Wizard state
    state = fields.Selection(
        [("confirm", "Confirm"), ("done", "Done")],
        default="confirm",
        readonly=True,
    )
    dry_run = fields.Boolean(
        string="Dry Run (simulate only)",
        default=True,
        help="When enabled, no database is actually created. "
             "Useful for validating the configuration before committing. "
             "A dry run never activates the tenant.",
    )

    # Output
    result_success = fields.Boolean(readonly=True)
    result_message = fields.Char(readonly=True)
    result_log = fields.Text(string="Provisioning Log", readonly=True)

    # ── Validation ────────────────────────────────────────────────────────

    @api.constrains("tenant_id")
    def _check_tenant_state(self):
        for rec in self:
            if rec.tenant_id.state not in ("draft", "provisioning"):
                raise UserError(
                    _("Tenant '%(name)s' is already in state '%(state)s'. "
                      "Only draft or provisioning tenants can be (re-)provisioned.",
                      name=rec.tenant_id.name, state=rec.tenant_id.state)
                )

    # ── Actions ───────────────────────────────────────────────────────────

    def action_run_provisioning(self):
        """Execute provisioning and show the result."""
        self.ensure_one()
        tenant = self.tenant_id

        tenant._check_can_provision()

        # Validate readiness
        tenant._check_provision_ready()

        # Pick the provisioner before touching the tenant, so a refusal
        # changes nothing. The checkbox decides: ticked never creates
        # anything; unticked creates a real database or refuses.
        try:
            provisioner = get_provisioner(odoo_env=self.env, dry_run=self.dry_run)
        except ProvisioningDisabled as exc:
            raise UserError(_(
                "This server is not allowed to create tenant databases. "
                "Tick 'Dry Run' to check the configuration, or ask the "
                "platform owner to enable real provisioning.")) from exc

        # Transition tenant to provisioning state
        if tenant.state == "draft":
            tenant.write({"state": "provisioning"})
            tenant.message_post(body=_("Provisioning initiated via wizard."))

        result = provisioner.run(tenant)
        tenant._apply_provision_result(result)

        self.write({
            "state": "done",
            "result_success": result.success,
            "result_message": result.message,
            "result_log": result.log,
        })

        # Keep wizard open to show result
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_close(self):
        return {"type": "ir.actions.act_window_close"}
