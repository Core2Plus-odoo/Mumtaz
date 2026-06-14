import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$")
_DOMAIN_RE = re.compile(
    r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class MumtazTenant(models.Model):
    _inherit = "mumtaz.tenant"

    erp_url = fields.Char(
        string="ERP URL", compute="_compute_erp_url",
        help="Public URL where this tenant's ERP is reachable.",
    )

    @api.model
    def _erp_base_domain(self):
        return (self.env["ir.config_parameter"].sudo().get_param(
            "mumtaz.erp_base_domain") or "erp.mumtaz.digital").strip(".").lower()

    @api.depends("subdomain", "custom_domain")
    def _compute_erp_url(self):
        base = self._erp_base_domain()
        for tenant in self:
            if tenant.custom_domain:
                tenant.erp_url = "https://%s" % tenant.custom_domain
            elif tenant.subdomain:
                tenant.erp_url = "https://%s.%s" % (tenant.subdomain, base)
            else:
                tenant.erp_url = False

    # ── Normalisation ─────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_routing_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_routing_vals(vals)
        return super().write(vals)

    @api.model
    def _normalize_routing_vals(self, vals):
        if vals.get("subdomain"):
            vals["subdomain"] = vals["subdomain"].strip().lower() or False
        if vals.get("custom_domain"):
            vals["custom_domain"] = vals["custom_domain"].strip().lower() or False

    # ── Validation (no hard SQL constraint — avoids upgrade failures on
    #    pre-existing data; enforced going forward) ─────────────────────────
    @api.constrains("subdomain")
    def _check_subdomain(self):
        for tenant in self:
            sub = tenant.subdomain
            if not sub:
                continue
            if not _SUBDOMAIN_RE.match(sub):
                raise ValidationError(
                    "Subdomain '%s' is invalid. Use lowercase letters, digits and "
                    "hyphens only (e.g. 'acme')." % sub
                )
            dup = self.search([("subdomain", "=", sub), ("id", "!=", tenant.id)], limit=1)
            if dup:
                raise ValidationError(
                    "Subdomain '%s' is already used by tenant '%s'." % (sub, dup.name)
                )

    @api.constrains("custom_domain")
    def _check_custom_domain(self):
        for tenant in self:
            dom = tenant.custom_domain
            if not dom:
                continue
            if not _DOMAIN_RE.match(dom):
                raise ValidationError(
                    "Custom domain '%s' is not a valid fully-qualified domain "
                    "name (e.g. 'erp.acmebank.com')." % dom
                )
            dup = self.search(
                [("custom_domain", "=", dom), ("id", "!=", tenant.id)], limit=1)
            if dup:
                raise ValidationError(
                    "Custom domain '%s' is already used by tenant '%s'."
                    % (dom, dup.name)
                )

    # ── Host resolution (used by routing layer / probe) ───────────────────
    @api.model
    def _subdomain_from_host(self, host):
        """Return the subdomain label for a host under the ERP base domain,
        '' for the bare base domain, or None when the host is not under it."""
        h = (host or "").split(":")[0].lower().strip(".")
        base = self._erp_base_domain()
        if not h or h == base:
            return ""
        if h.endswith("." + base):
            return h[: -(len(base) + 1)].split(".")[-1]
        return None

    @api.model
    def _resolve_for_host(self, host):
        """Return the active tenant matching this host, or an empty recordset."""
        h = (host or "").split(":")[0].lower().strip(".")
        sub = self._subdomain_from_host(host)
        if sub:
            tenant = self.sudo().search(
                [("state", "=", "active"), ("subdomain", "=", sub)], limit=1)
            if tenant:
                return tenant
        if h:
            return self.sudo().search(
                [("state", "=", "active"), ("custom_domain", "=", h)], limit=1)
        return self.browse()

    @api.model
    def _db_for_host(self, host):
        tenant = self._resolve_for_host(host)
        return tenant.database_name if tenant else False
