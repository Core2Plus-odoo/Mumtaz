from odoo import fields, models


class MumtazSmeSignup(models.Model):
    _name = "mumtaz.sme.signup"
    _description = "SME Self-Service Signup"
    _rec_name = "company_name"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    org_id = fields.Many2one(
        "mumtaz.organization", string="Organisation", required=True,
        ondelete="cascade", tracking=True,
    )

    # ── Applicant info ────────────────────────────────────────────────
    company_name = fields.Char(string="Company Name", required=True, tracking=True)
    contact_name = fields.Char(string="Contact Name", required=True)
    email = fields.Char(required=True, tracking=True)
    phone = fields.Char()
    country_id = fields.Many2one("res.country", string="Country")
    industry = fields.Char()
    website = fields.Char()
    message = fields.Text(string="How did you hear about us / additional info")

    # ── Processing ────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("new", "New"),
            ("reviewed", "Reviewed"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="new",
        tracking=True,
    )
    reviewer_notes = fields.Text()
    partner_id = fields.Many2one(
        "res.partner", string="Created Partner",
        help="Populated when signup is converted to an Odoo partner.",
    )

    def action_approve(self):
        for rec in self:
            rec.state = "approved"
            if not rec.partner_id:
                partner = self.env["res.partner"].create({
                    "name": rec.company_name,
                    "email": rec.email,
                    "phone": rec.phone,
                    "is_company": True,
                    "country_id": rec.country_id.id,
                    "website": rec.website,
                })
                rec.partner_id = partner

    def action_reject(self):
        self.write({"state": "rejected"})
