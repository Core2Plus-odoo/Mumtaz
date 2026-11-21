import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

STAGING_DB_PREFIX = "stg_"


class MumtazTenantProvisioning(models.Model):
    """Provisioning state, queue and outcome handling for tenants.

    The provision wizard runs provisioning inline (good for a dry run or a
    small bundle). A full ERP bundle takes minutes, so production use goes
    through the queue and the scheduled worker.
    """
    _inherit = "mumtaz.tenant"

    environment = fields.Selection(
        [("staging", "Staging"), ("production", "Production")],
        tracking=True,
        help="Staging tenants hold trial or test data. Their database name "
             "always starts with 'stg_' so that backups, monitoring and "
             "clean-up can tell them apart from production. Empty on tenants "
             "created before this field existed.",
    )
    provision_queued = fields.Boolean(
        string="Queued for Provisioning", default=False, copy=False, readonly=True,
        help="Set when the tenant is waiting for the background provisioning worker.",
    )
    provision_queued_on = fields.Datetime(readonly=True, copy=False)
    workspace_url = fields.Char(
        string="Workspace Address", compute="_compute_workspace_url",
        help="Where the tenant's users sign in.",
    )
    access_link = fields.Char(
        string="Administrator Set-Password Link", copy=False, readonly=True,
        groups="mumtaz_tenant_manager.group_mumtaz_platform_admin",
        help="One-time link issued by the tenant database at provisioning. "
             "It lets the tenant administrator choose a password. It expires "
             "on its own and stops working after the first sign-in. Treat it "
             "as a credential.",
    )
    access_link_issued_on = fields.Datetime(readonly=True, copy=False)
    database_needs_cleanup = fields.Boolean(
        string="Incomplete Database Left Behind", copy=False, readonly=True,
        help="A provisioning run created the database and then failed. The "
             "database is never dropped automatically.",
    )

    @api.depends("subdomain", "custom_domain")
    def _compute_workspace_url(self):
        # sudo: system parameter; only administrators may read ir.config_parameter
        base = (self.env["ir.config_parameter"].sudo().get_param("mumtaz.erp_base_domain")
                or "erp.mumtaz.digital")
        for rec in self:
            if rec.custom_domain:
                rec.workspace_url = "https://%s" % rec.custom_domain
            elif rec.subdomain:
                rec.workspace_url = "https://%s.%s" % (rec.subdomain, base)
            else:
                rec.workspace_url = False

    @api.constrains("environment", "database_name")
    def _check_environment_database_name(self):
        for rec in self:
            name = rec.database_name or ""
            if rec.environment == "staging" and not name.startswith(STAGING_DB_PREFIX):
                raise ValidationError(_(
                    "A staging tenant's database name must start with "
                    "'%(prefix)s' (got '%(db)s').",
                    prefix=STAGING_DB_PREFIX, db=name))
            if rec.environment == "production" and name.startswith(STAGING_DB_PREFIX):
                raise ValidationError(_(
                    "A production tenant's database name must not start with "
                    "'%(prefix)s' (got '%(db)s').",
                    prefix=STAGING_DB_PREFIX, db=name))

    # ── Permission ────────────────────────────────────────────────────────

    def _check_can_provision(self):
        """Creating a database is for platform administrators only.

        The Platform Manager group may edit tenant records, so the model's
        access rights alone do not protect the provisioning methods.
        """
        if self.env.su:
            return
        user = self.env.user
        if (user.has_group("mumtaz_tenant_manager.group_mumtaz_platform_admin")
                or user.has_group("base.group_system")):
            return
        raise AccessError(_("Only a Platform Administrator can provision a tenant."))

    # ── Queue ─────────────────────────────────────────────────────────────

    def action_reset_to_draft(self):
        # Clearing the queue flag prevents an orphaned queued+draft tenant.
        self.write({"provision_queued": False})
        return super().action_reset_to_draft()

    def action_queue_provisioning(self):
        self._check_can_provision()
        for tenant in self:
            tenant._check_provision_ready()
            tenant.write({
                "state": "provisioning",
                "provision_queued": True,
                "provision_queued_on": fields.Datetime.now(),
            })
            tenant.message_post(body=_("Queued for background provisioning."))
        return True

    @api.model
    def _cron_run_provision_queue(self, limit=1):
        """Process queued tenants one at a time. Each is claimed (flag cleared)
        and committed before provisioning so a crash never loops forever."""
        from ..services.provisioning import get_provisioner

        queued = self.search(
            [("provision_queued", "=", True), ("state", "=", "provisioning")],
            order="provision_queued_on asc", limit=limit,
        )
        for tenant in queued:
            # Claim the job first and commit, so a failure does not retry.
            tenant.provision_queued = False
            self.env.cr.commit()

            provisioner = get_provisioner(odoo_env=self.env)
            result = provisioner.run(tenant)
            tenant._apply_provision_result(result)
            self.env.cr.commit()
        return True

    # ── Outcome ───────────────────────────────────────────────────────────

    def _apply_provision_result(self, result):
        """Record what a provisioning run did. The single place that may move
        a tenant to ``active`` after provisioning.

        A simulated (dry-run) success leaves the tenant in draft: nothing
        exists yet, so nothing is active.
        """
        self.ensure_one()
        self._append_log(result.log)
        if result.success and not result.simulated:
            vals = {
                "state": "active",
                "provisioned_on": fields.Datetime.now(),
                "admin_password": False,
                "database_needs_cleanup": False,
            }
            if result.access_link:
                vals.update(access_link=result.access_link,
                            access_link_issued_on=fields.Datetime.now())
            self.write(vals)
            self.message_post(body=_("Provisioning completed and verified."))
        elif result.success:
            self.write({"state": "draft"})
            self.message_post(body=_(
                "Dry run passed. Nothing was created; the tenant stays in draft."))
        else:
            vals = {"state": "draft"}
            if result.database_created:
                # Only ever set here; a person clears it after dealing with
                # the database.
                vals["database_needs_cleanup"] = True
            self.write(vals)
            self.message_post(body=_("Provisioning failed. See the provisioning log."))
        return result
