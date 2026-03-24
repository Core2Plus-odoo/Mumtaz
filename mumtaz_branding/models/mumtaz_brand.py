from odoo import api, fields, models


class MumtazBrand(models.Model):
    _name = "mumtaz.brand"
    _description = "Mumtaz White-Label Brand Configuration"
    _rec_name = "brand_name"
    _order = "brand_name"
    _inherit = ["mail.thread"]

    # ── Identity ──────────────────────────────────────────────────────
    brand_name = fields.Char(
        required=True, tracking=True,
        help="Internal reference name for this brand configuration.",
    )
    partner_name = fields.Char(
        required=True, tracking=True,
        help="Public-facing brand name shown to end users and in communications.",
    )
    product_name = fields.Char(
        required=True, default="Mumtaz", tracking=True,
        help="Platform name displayed to end users (e.g. 'MyBank Business Suite').",
    )
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text(string="Internal Notes")

    # ── Visual Identity ────────────────────────────────────────────────
    logo = fields.Binary(string="Brand Logo", attachment=True)
    logo_filename = fields.Char()
    favicon = fields.Binary(string="Favicon", attachment=True)
    favicon_filename = fields.Char()
    primary_color = fields.Char(
        string="Primary Color", default="#0f3460",
        help="Hex color code for headers and primary UI elements.",
    )
    secondary_color = fields.Char(
        string="Secondary Color", default="#16213e",
        help="Hex color code for gradients and secondary accents.",
    )

    # ── Email ─────────────────────────────────────────────────────────
    email_from_name = fields.Char(
        string="Sender Display Name",
        help="Name shown as email sender (e.g. 'Acme Bank — Business Platform').",
    )
    email_footer = fields.Html(
        string="Email Footer",
        help="HTML block appended to outgoing system emails under this brand.",
    )

    # ── Report Branding ───────────────────────────────────────────────
    report_header = fields.Binary(string="Report Header Image", attachment=True)
    report_header_filename = fields.Char()
    report_footer_text = fields.Text(
        help="Text included in PDF report footers for this brand.",
    )

    # ── Portal / Onboarding Welcome ───────────────────────────────────
    portal_welcome_title = fields.Char(
        string="Welcome Screen Title",
        help="Headline shown on the portal or new-user welcome screen.",
    )
    portal_welcome_body = fields.Html(
        string="Welcome Screen Body",
        help="Rich-text welcome message shown to new users registering under this brand.",
    )

    # ── Scope ─────────────────────────────────────────────────────────
    company_ids = fields.Many2many(
        "res.company",
        "mumtaz_brand_company_rel",
        "brand_id",
        "company_id",
        string="Companies",
        help="Companies operating under this brand configuration.",
    )
    _sql_constraints = [
        ("mumtaz_brand_name_unique", "unique(brand_name)",
         "Brand name must be unique across the platform."),
    ]
