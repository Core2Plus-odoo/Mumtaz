from odoo import api, fields, models


class MumtazTenantSmeExtension(models.Model):
    """
    Extends mumtaz.tenant with the inverse side of the SME profile relationship.
    Defined here (in mumtaz_sme_profile) to avoid a circular dependency:
    mumtaz_tenant_manager cannot depend on mumtaz_sme_profile because
    mumtaz_sme_profile already depends on mumtaz_tenant_manager.
    """

    _inherit = "mumtaz.tenant"

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

    @api.depends("sme_profile_ids")
    def _compute_sme_profile_count(self):
        for rec in self:
            rec.sme_profile_count = len(rec.sme_profile_ids)
