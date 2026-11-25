from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .secret_guard import check_vault_ref, refuse_secret

LEAD_GROUP = "c2p_project_tracker.group_c2p_delivery_lead"


class C2pClientAccess(models.Model):
    """Who holds which access to a client's systems, and where the credential
    lives.

    There is deliberately no chatter on this model and no free-text notes
    field: both are places a password ends up. The audit trail is the explicit
    granted/revoked fields.
    """

    _name = "c2p.client.access"
    _description = "C2P Client Access Register"
    _order = "partner_id, state, id desc"

    name = fields.Char(
        string="Access", required=True,
        help="What the access is to, e.g. 'Odoo production – administrator'.")
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, index=True,
        ondelete="cascade", domain="[('c2p_is_client', '=', True)]")
    instance_id = fields.Many2one(
        "c2p.client.instance", string="Instance", index=True,
        domain="[('partner_id', '=', partner_id)]")
    # Empty by default: a client is shared by Consultants and Solutions, and
    # the Solutions delivery owner must see what Consultants recorded. Set a
    # company to restrict a row to it.
    company_id = fields.Many2one("res.company", index=True)
    holder_id = fields.Many2one(
        "res.partner", string="Held By", required=True, index=True,
        help="The person who holds this access: a C2P employee or a "
             "subcontractor contact.")
    access_level = fields.Selection(
        [("read", "Read-only"), ("user", "User"), ("admin", "Administrator"),
         ("server", "Server / hosting"), ("api", "API / integration")],
        required=True, default="user")
    credential_kind = fields.Selection(
        [("named", "Personal named account (no shared secret)"),
         ("shared", "Shared credential (kept in the vault)")],
        required=True, default="named")
    vault_ref = fields.Char(
        string="Vault Reference",
        help="Where the credential is kept, as vault://collection/item. "
             "Never the credential itself.")
    purpose = fields.Char()
    state = fields.Selection(
        [("requested", "Requested"), ("active", "Active"),
         ("revoked", "Revoked")],
        default="requested", required=True, index=True, copy=False)
    granted_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    granted_on = fields.Datetime(readonly=True, copy=False)
    expires_on = fields.Date(string="Expires")
    revoked_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    revoked_on = fields.Datetime(readonly=True, copy=False)
    is_expired = fields.Boolean(compute="_compute_is_expired")

    @api.depends("expires_on", "state")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for row in self:
            row.is_expired = bool(
                row.state == "active" and row.expires_on
                and row.expires_on < today)

    @api.constrains("vault_ref")
    def _check_vault_ref(self):
        for row in self:
            check_vault_ref(row.vault_ref)

    @api.constrains("name", "purpose")
    def _check_no_secret(self):
        for row in self:
            for fname in ("name", "purpose"):
                refuse_secret(row._fields[fname].string, row[fname])

    @api.constrains("instance_id", "partner_id")
    def _check_instance_client(self):
        for row in self:
            if row.instance_id and row.instance_id.partner_id != row.partner_id:
                raise ValidationError(_(
                    "Instance %s belongs to a different client.",
                    row.instance_id.display_name))

    def write(self, vals):
        if not self.env.context.get("c2p_onboarding_transition") and any(
                k in vals for k in ("state", "granted_by_id", "granted_on",
                                    "revoked_by_id", "revoked_on")):
            raise UserError(_(
                "Use Grant or Revoke so the register records who did it."))
        return super().write(vals)

    def _c2p_require_lead(self):
        if not self.env.user.has_group(LEAD_GROUP):
            raise AccessError(_(
                "Only a Delivery Lead or Portfolio Manager can grant or "
                "revoke client access."))

    def action_grant(self):
        self._c2p_require_lead()
        for row in self:
            if row.state != "requested":
                raise UserError(_("Only a requested access can be granted."))
            if row.credential_kind == "shared" and not row.vault_ref:
                raise UserError(_(
                    "A shared credential needs its vault reference before the "
                    "access is recorded as granted."))
        self.with_context(c2p_onboarding_transition=True).write({
            "state": "active", "granted_by_id": self.env.uid,
            "granted_on": fields.Datetime.now()})
        return True

    def action_revoke(self):
        self._c2p_require_lead()
        self.filtered(lambda r: r.state != "revoked").with_context(
            c2p_onboarding_transition=True).write({
                "state": "revoked", "revoked_by_id": self.env.uid,
                "revoked_on": fields.Datetime.now()})
        return True
