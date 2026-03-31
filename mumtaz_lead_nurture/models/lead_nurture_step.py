from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LeadNurtureStep(models.Model):
    """One step in a campaign sequence: email, WhatsApp message, or activity."""

    _name = "lead.nurture.step"
    _description = "Campaign Sequence Step"
    _order = "campaign_id, step_number"
    _rec_name = "name"

    campaign_id = fields.Many2one(
        "lead.nurture.campaign", required=True, ondelete="cascade", index=True
    )
    step_number = fields.Integer(required=True, default=1)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    # ── Channel ────────────────────────────────────────────────────────
    channel = fields.Selection(
        [
            ("email", "Email"),
            ("whatsapp", "WhatsApp"),
            ("activity", "Create Activity"),
        ],
        required=True,
        default="email",
    )
    delay_days = fields.Integer(
        default=1,
        help="Days to wait after the previous step (or enrollment for step 1).",
    )

    # ── Email ──────────────────────────────────────────────────────────
    mail_template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        domain=[("model", "=", "crm.lead")],
    )

    # ── WhatsApp ───────────────────────────────────────────────────────
    wa_template_id = fields.Many2one("lead.whatsapp.template", string="WhatsApp Template")

    # ── Activity ───────────────────────────────────────────────────────
    activity_type_id = fields.Many2one("mail.activity.type", string="Activity Type")
    activity_summary = fields.Char(string="Activity Summary")
    activity_note = fields.Text(string="Activity Note")
    activity_deadline_days = fields.Integer(
        default=2,
        help="Deadline for the created activity (days from today).",
    )

    # ── Scoring effect ────────────────────────────────────────────────
    score_on_send = fields.Integer(
        default=0,
        help="Score added to the lead when this step executes.",
    )

    @api.constrains("step_number")
    def _check_step_number(self):
        for rec in self:
            if rec.step_number < 1:
                raise ValidationError("Step number must be >= 1.")

    @api.constrains("channel", "mail_template_id", "wa_template_id", "activity_type_id")
    def _check_channel_config(self):
        for rec in self:
            if rec.channel == "email" and not rec.mail_template_id:
                raise ValidationError(f"Step '{rec.name}': Email channel requires an email template.")
            if rec.channel == "whatsapp" and not rec.wa_template_id:
                raise ValidationError(f"Step '{rec.name}': WhatsApp channel requires a WhatsApp template.")
