import datetime
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MumtazTenantProvisioning(models.Model):
    """Background provisioning queue for tenants.

    The provision wizard runs provisioning inline (good for one-off/manual
    runs and testing). For production, queue the tenant and let a cron worker
    run the (potentially heavy) database creation + module install out of the
    request cycle.
    """
    _inherit = "mumtaz.tenant"

    provision_queued = fields.Boolean(
        string="Queued for Provisioning", default=False, copy=False, readonly=True,
        help="Set when the tenant is waiting for the background provisioning worker.",
    )
    provision_queued_on = fields.Datetime(readonly=True, copy=False)

    def action_reset_to_draft(self):
        # Clearing the queue flag prevents an orphaned queued+draft tenant.
        self.write({"provision_queued": False})
        return super().action_reset_to_draft()

    def action_queue_provisioning(self):
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
            tenant._append_log(result.log)
            if result.success:
                tenant.write({
                    "state": "active",
                    "provisioned_on": datetime.datetime.utcnow(),
                    # admin_password already cleared by RealProvisioner._create_database
                })
                tenant.message_post(body=_("Background provisioning completed."))
            else:
                tenant.write({"state": "draft"})
                tenant.message_post(
                    body=_("Background provisioning failed. See provisioning log.")
                )
            self.env.cr.commit()
        return True
