from odoo import fields, models


class WhatsAppTemplate(models.Model):
    """WhatsApp message template with provider-agnostic body."""

    _name = "lead.whatsapp.template"
    _description = "WhatsApp Template"
    _order = "name"
    _rec_name = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    provider_id = fields.Many2one("lead.whatsapp.provider", string="Provider")

    body = fields.Text(
        required=True,
        help=(
            "Message body. Available placeholders:\n"
            "  {company_name}  {contact_name}  {email}  {phone}\n"
            "  {city}  {industry}  {use_case}"
        ),
    )
    language = fields.Char(default="en")

    # Meta WhatsApp Cloud: pre-approved template details
    wa_template_name = fields.Char(
        string="Approved Template Name",
        help="Exact template name as approved in Meta Business Manager.",
    )
    wa_template_language = fields.Char(default="en_US")

    notes = fields.Text()

    def render_body(self, lead):
        """Render message body with lead placeholders."""
        self.ensure_one()
        vals = {
            "company_name": lead.partner_name or lead.name or "",
            "contact_name": lead.contact_name or "",
            "email": lead.email_from or "",
            "phone": lead.phone or lead.mobile or "",
            "city": lead.city or "",
            "industry": lead.industry_cluster or "",
            "use_case": lead.use_case_type or "",
        }
        try:
            return self.body.format(**vals)
        except (KeyError, ValueError):
            return self.body
