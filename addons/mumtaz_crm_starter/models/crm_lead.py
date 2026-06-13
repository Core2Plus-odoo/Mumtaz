from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    x_lead_source = fields.Selection(
        [("website", "Website"), ("referral", "Referral"), ("exhibition", "Exhibition"),
         ("whatsapp", "WhatsApp"), ("cold_call", "Cold Call"), ("linkedin", "LinkedIn"),
         ("other", "Other")],
        string="Lead Source",
    )
    x_next_followup = fields.Date(string="Next Follow-up")
