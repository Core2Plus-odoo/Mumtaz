import re
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

# Hostnames an organization must never be given as its workspace address.
RESERVED_CODES = {
    "www", "app", "erp", "api", "admin", "mail", "smtp", "ftp", "zaki",
    "jewel", "jawhar", "pharma", "delivery", "marketplace", "ig2", "c2p",
    "staging", "status", "support", "billing", "portal", "demo", "test",
}
OPEN_STATES = ("new", "approved", "provisioning")


class MumtazSignupRequest(models.Model):
    """An organization asking for a product.

    The record carries the whole journey and nothing is skipped on the way:

        new ─approve→ approved ─provision→ provisioning ─(worker)→ ready
                                                               └→ failed

    Approval is a person's decision. It creates the organization's contact
    card, the tenant record (staging) and the trial subscription that grants
    the entitlement. Provisioning is refused without that entitlement. The
    request only becomes `ready` when the provisioning worker reports a real,
    verified database — a dry run sends it back to `approved`.
    """

    _name = "mumtaz.signup.request"
    _description = "Organization Registration Request"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(string="Organization", required=True, tracking=True)
    contact_name = fields.Char(required=True)
    email = fields.Char(required=True, tracking=True)
    phone = fields.Char()
    country_id = fields.Many2one("res.country")
    product_id = fields.Many2one(
        "mumtaz.product", required=True, ondelete="restrict", tracking=True,
        domain="[('self_service', '=', True)]",
    )
    plan_id = fields.Many2one(
        "mumtaz.plan", required=True, ondelete="restrict", tracking=True,
        domain="[('product_id', '=', product_id)]",
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("approved", "Approved"),
            ("provisioning", "Provisioning"),
            ("ready", "Ready"),
            ("failed", "Failed"),
            ("rejected", "Rejected"),
        ],
        default="new", required=True, readonly=True, copy=False, tracking=True,
    )
    source = fields.Selection(
        [("operator", "Entered by an operator"), ("public", "Public form")],
        default="operator", required=True, readonly=True, copy=False,
    )
    reject_reason = fields.Text(copy=False)

    partner_id = fields.Many2one(
        "res.partner", string="Organization Record", readonly=True, copy=False)
    tenant_id = fields.Many2one(
        "mumtaz.tenant", string="Tenant", readonly=True, copy=False)
    subscription_id = fields.Many2one(
        "mumtaz.subscription", string="Subscription", readonly=True, copy=False)
    workspace_url = fields.Char(related="tenant_id.workspace_url")
    entitlement_granted = fields.Boolean(compute="_compute_entitlement")
    entitlement_reason = fields.Char(compute="_compute_entitlement")

    # ── Validation ────────────────────────────────────────────────────────

    @api.constrains("email")
    def _check_email(self):
        for rec in self:
            if not tools.email_normalize(rec.email or ""):
                raise ValidationError(_("'%s' is not a valid email address.", rec.email))

    @api.constrains("product_id", "plan_id")
    def _check_plan_matches_product(self):
        for rec in self:
            if rec.plan_id.product_id != rec.product_id:
                raise ValidationError(_(
                    "Plan '%(plan)s' does not belong to product '%(product)s'.",
                    plan=rec.plan_id.name, product=rec.product_id.name))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.plan_id.product_id != self.product_id:
            self.plan_id = self.product_id.plan_ids[:1]

    # ── Entitlement ───────────────────────────────────────────────────────

    def _entitlement(self):
        """What the feature-access service says about this organization's
        right to the product, today."""
        self.ensure_one()
        feature = self.product_id.access_feature_id
        if not self.tenant_id:
            return {"effective_enabled": False, "reason": _("No tenant yet.")}
        if not feature:
            return {"effective_enabled": False,
                    "reason": _("The product has no access feature.")}
        return self.env["mumtaz.feature.access.service"].resolve_feature_access(
            self.tenant_id, feature, include_quota=False)

    @api.depends("tenant_id", "subscription_id.status", "subscription_id.is_current",
                 "product_id.access_feature_id")
    def _compute_entitlement(self):
        for rec in self:
            result = rec._entitlement()
            rec.entitlement_granted = bool(result.get("effective_enabled"))
            rec.entitlement_reason = result.get("reason")

    # ── Permission ────────────────────────────────────────────────────────

    def _check_can_decide(self):
        """Approving commits the company to a tenant and a subscription;
        provisioning creates a database. Both are for the control plane's
        administrators."""
        if self.env.su:
            return
        if self.env.user.has_group("mumtaz_control_plane.group_mumtaz_super_admin"):
            return
        raise AccessError(_(
            "Only a Mumtaz Super Admin can approve or provision a registration request."))

    # ── Helpers ───────────────────────────────────────────────────────────

    def _unique_tenant_code(self):
        self.ensure_one()
        base = re.sub(r"[^a-z0-9]+", "-", (self.name or "").lower()).strip("-")[:24].strip("-")
        if len(base) < 3:
            base = ("org-%s" % base).strip("-")
        if base in RESERVED_CODES:
            base = "%s-org" % base
        # sudo: uniqueness must be checked against every tenant, including archived ones
        Tenant = self.env["mumtaz.tenant"].sudo().with_context(active_test=False)
        candidate, n = base, 1
        while Tenant.search_count([
            "|", ("code", "=", candidate),
            ("database_name", "=", self._database_name(candidate)),
        ]):
            n += 1
            candidate = "%s-%d" % (base, n)
        return candidate

    @staticmethod
    def _database_name(code):
        return "stg_%s" % code.replace("-", "_")

    def _ensure_partner(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        # sudo: the approval creates the organization's contact card; approvers need not hold Contact Creation
        Partner = self.env["res.partner"].sudo()
        company = Partner.create({
            "name": self.name,
            "is_company": True,
            "email": tools.email_normalize(self.email),
            "phone": self.phone,
            "country_id": self.country_id.id,
        })
        Partner.create({
            "name": self.contact_name,
            "parent_id": company.id,
            "type": "contact",
            "email": tools.email_normalize(self.email),
        })
        return company

    # ── Actions ───────────────────────────────────────────────────────────

    def action_approve(self):
        self._check_can_decide()
        for rec in self:
            if rec.state != "new":
                raise UserError(_("Only a new request can be approved."))
            product, plan = rec.product_id, rec.plan_id
            if not product.self_service or product.status == "planned":
                raise UserError(_(
                    "%s is not open to registration requests.", product.name))
            bundle = plan.legacy_bundle_id or product.bundle_id
            if not bundle:
                raise UserError(_(
                    "Plan '%s' has no install profile, so nothing could be provisioned.",
                    plan.name))

            partner = rec._ensure_partner()
            code = rec._unique_tenant_code()
            tenant = self.env["mumtaz.tenant"].create({
                "name": rec.name,
                "code": code,
                "database_name": rec._database_name(code),
                "subdomain": code,
                "environment": "staging",
                "bundle_id": bundle.id,
                "admin_email": tools.email_normalize(rec.email),
                "admin_name": rec.contact_name,
                "customer_partner_id": partner.id,
            })
            today = fields.Date.context_today(rec)
            subscription = self.env["mumtaz.subscription"].create({
                "tenant_id": tenant.id,
                "plan_id": plan.id,
                "status": "trial",
                "billing_cycle": plan.billing_cycle_default,
                "start_date": today,
                "trial_start": today,
                "trial_end": today + timedelta(days=max(plan.trial_days, 1)),
                "currency_id": plan.currency_id.id,
                "is_current": True,
            })
            rec.write({
                "state": "approved",
                "partner_id": partner.id,
                "tenant_id": tenant.id,
                "subscription_id": subscription.id,
            })
            entitlement = rec._entitlement()
            if not entitlement.get("effective_enabled"):
                # Raising rolls the whole approval back: no half-made tenant.
                raise UserError(_(
                    "Plan '%(plan)s' does not grant access to %(product)s "
                    "(%(reason)s). Fix the plan's features before approving.",
                    plan=plan.name, product=product.name,
                    reason=entitlement.get("reason")))
            rec.message_post(body=_(
                "Approved. Tenant %(code)s (staging) and a %(days)s-day trial on "
                "%(plan)s were created. No database exists yet.",
                code=code, days=plan.trial_days, plan=plan.name))
        return True

    def action_provision(self):
        self._check_can_decide()
        for rec in self:
            if rec.state not in ("approved", "failed"):
                raise UserError(_("Approve the request before provisioning it."))
            entitlement = rec._entitlement()
            if not entitlement.get("effective_enabled"):
                raise UserError(_(
                    "%(org)s has no entitlement to %(product)s: %(reason)s",
                    org=rec.name, product=rec.product_id.name,
                    reason=entitlement.get("reason")))
            if rec.tenant_id.database_needs_cleanup:
                raise UserError(_(
                    "An earlier run left database '%s' behind. An administrator "
                    "must inspect and remove it first.", rec.tenant_id.database_name))
            rec.tenant_id.action_queue_provisioning()
            rec.state = "provisioning"
            rec.message_post(body=_("Queued for provisioning."))
        return True

    def action_reject(self):
        self._check_can_decide()
        for rec in self:
            if rec.state != "new":
                raise UserError(_("Only a new request can be rejected."))
            rec.state = "rejected"
        return True

    def _on_provision_result(self, result):
        """Called by the tenant when a provisioning run ends."""
        for rec in self:
            if result.success and not result.simulated:
                rec.state = "ready"
                rec.message_post(body=_(
                    "Workspace ready at %s. The administrator's set-password "
                    "link is on the tenant record.", rec.workspace_url))
            elif result.success:
                rec.state = "approved"
                rec.message_post(body=_(
                    "Dry run only: this server is not allowed to create "
                    "databases, so nothing was provisioned."))
            else:
                rec.state = "failed"
                rec.message_post(body=_("Provisioning failed: %s", result.message))

    # ── Public intake ─────────────────────────────────────────────────────

    @api.model
    def _public_signup_enabled(self):
        # sudo: system parameter; only administrators may read ir.config_parameter
        return self.env["ir.config_parameter"].sudo().get_param(
            "mumtaz_control_plane.public_signup") == "1"

    @api.model
    def _register_public(self, payload):
        """Record a request made on the public form. Called by the controller
        with a sudo environment.

        It only ever creates a `new` request. It never creates a tenant, a
        subscription or a database: a person approves first.
        Returns True when a request is on file for this email and product.
        """
        if not self._public_signup_enabled():
            raise UserError(_("Registration is not open."))
        if (payload.get("website") or "").strip():
            # Honeypot field: a person never fills it. Say nothing useful.
            return True

        name = (payload.get("organization") or "").strip()
        contact = (payload.get("contact_name") or "").strip()
        email = tools.email_normalize((payload.get("email") or "").strip())
        if not (2 <= len(name) <= 120):
            raise UserError(_("Please give your organization's name."))
        if not (2 <= len(contact) <= 120):
            raise UserError(_("Please give your name."))
        if not email:
            raise UserError(_("Please give a valid email address."))

        product = self.env["mumtaz.product"].search([
            ("code", "=", (payload.get("product") or "").strip()),
            ("self_service", "=", True),
            ("status", "!=", "planned"),
        ], limit=1)
        plan = product.plan_ids.filtered("active")[:1]
        if not product or not plan:
            raise UserError(_("That product is not open for registration."))

        if self.search_count([
            ("email", "=", email), ("product_id", "=", product.id),
            ("state", "in", OPEN_STATES),
        ]):
            # Same answer as a new request, so the form cannot be used to
            # find out who has already registered.
            return True

        # sudo: system parameter; only administrators may read ir.config_parameter
        cap = int(self.env["ir.config_parameter"].sudo().get_param(
            "mumtaz_control_plane.public_signup_hourly_cap", 20))
        recent = self.search_count([
            ("source", "=", "public"),
            ("create_date", ">=", fields.Datetime.now() - timedelta(hours=1)),
        ])
        if recent >= cap:
            raise UserError(_("We are receiving many requests. Please try again later."))

        country = self.env["res.country"].search(
            [("code", "=", (payload.get("country") or "").strip().upper())], limit=1)
        self.create({
            "name": name,
            "contact_name": contact,
            "email": email,
            "phone": (payload.get("phone") or "").strip()[:40] or False,
            "country_id": country.id,
            "product_id": product.id,
            "plan_id": plan.id,
            "source": "public",
        })
        return True
