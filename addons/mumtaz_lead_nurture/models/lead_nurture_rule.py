from odoo import fields, models


TRIGGER_EVENTS = [
    ("lead_enrolled", "Lead Enrolled in Campaign"),
    ("email_sent", "Email Sent"),
    ("email_opened", "Email Opened"),
    ("email_clicked", "Email Clicked"),
    ("whatsapp_sent", "WhatsApp Sent"),
    ("reply_received", "Reply Received"),
    ("positive_reply", "Positive Reply"),
    ("demo_requested", "Demo Requested"),
    ("requirement_shared", "Requirement Shared"),
    ("manual_qualified", "Manually Qualified"),
    ("not_interested", "Marked Not Interested"),
    ("bounced", "Message Bounced"),
]


class LeadNurtureRule(models.Model):
    """Scoring rule: on event X, apply score_change to the lead."""

    _name = "lead.nurture.rule"
    _description = "Lead Qualification Rule"
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    trigger_event = fields.Selection(TRIGGER_EVENTS, required=True)
    score_change = fields.Integer(
        required=True,
        help="Positive value adds score; negative value subtracts.",
    )
    description = fields.Text()
