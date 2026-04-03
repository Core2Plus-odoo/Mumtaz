from odoo import fields, models


class LeadNurtureLog(models.Model):
    """Immutable communication history record for a lead."""

    _name = "lead.nurture.log"
    _description = "Lead Communication Log"
    _order = "timestamp desc"
    _rec_name = "subject"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade", index=True)
    campaign_id = fields.Many2one("lead.nurture.campaign", ondelete="set null")
    step_id = fields.Many2one("lead.nurture.step", ondelete="set null")

    channel = fields.Selection(
        [
            ("email", "Email"),
            ("whatsapp", "WhatsApp"),
            ("activity", "Activity"),
            ("manual", "Manual"),
        ],
        required=True,
    )
    status = fields.Selection(
        [
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("opened", "Opened"),
            ("clicked", "Clicked"),
            ("replied", "Replied"),
            ("bounced", "Bounced"),
            ("failed", "Failed"),
        ],
        default="sent",
        required=True,
    )

    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)
    subject = fields.Char()
    body_preview = fields.Text()
    provider_ref = fields.Char(
        string="Provider Reference",
        help="External message ID or reference from the sending provider.",
    )
    response_summary = fields.Text()
    score_change = fields.Integer(string="Score Change")

    # Denormalized for fast display
    lead_name = fields.Char(related="lead_id.name", store=True)
    campaign_name = fields.Char(related="campaign_id.name", store=True)
