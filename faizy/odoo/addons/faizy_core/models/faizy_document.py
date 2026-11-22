from odoo import api, fields, models


class FaizyDocument(models.Model):
    """The family document vault.

    Passports, CNICs, medical cards, utility bills — the paperwork someone
    living abroad needs a person on the ground to act on. Held against the family member so a
    Faizy sent to renew a CNIC has the number to hand without the customer
    digging through WhatsApp history at 2am.

    Deliberately restricted: these are identity documents. Read access is the
    owning customer plus Operations, never the whole staff group and never the
    assigned worker by default.
    """

    _name = "faizy.document"
    _description = "Faizy Family Document"
    _inherit = ["mail.thread"]
    _order = "expiry_date, name"

    # Marks records created by the sample-data loader so they can all be
    # removed together without touching anything real.
    is_sample = fields.Boolean(default=False, copy=False, index=True)

    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, index=True, ondelete="cascade"
    )
    family_member_id = fields.Many2one(
        "faizy.family.member",
        string="Belongs To",
        index=True,
        domain="[('partner_id', '=', partner_id)]",
    )
    doc_type = fields.Selection(
        [
            ("cnic", "CNIC"),
            ("passport", "Passport"),
            ("b_form", "B-Form"),
            ("medical", "Medical Record"),
            ("prescription", "Prescription"),
            ("utility", "Utility Bill"),
            ("property", "Property Document"),
            ("other", "Other"),
        ],
        default="other",
        required=True,
        tracking=True,
    )
    reference = fields.Char(
        string="Document Number",
        help="CNIC or passport number. Visible to Operations only.",
        groups="faizy_core.group_faizy_ops",
    )
    # The scan itself and its notes are Operations-only (FAIZY HQ05 S4).
    # Customer care (Faizy / Agent) still sees that a document exists, its
    # type and its expiry, which is what a reminder conversation needs, but
    # not the CNIC, passport or medical file. Portal stays in the list so a
    # customer can still reach their own file; the portal record rule above
    # keeps that to their own documents only.
    attachment = fields.Binary(
        string="File",
        attachment=True,
        groups="faizy_core.group_faizy_ops,base.group_portal",
    )
    attachment_name = fields.Char(groups="faizy_core.group_faizy_ops,base.group_portal")

    issue_date = fields.Date()
    expiry_date = fields.Date(
        tracking=True,
        help="Drives the renewal reminder. A passport nobody noticed had "
        "expired is the kind of thing families ask us to catch.",
    )
    days_to_expiry = fields.Integer(compute="_compute_expiry", store=True)
    expiry_state = fields.Selection(
        [
            ("valid", "Valid"),
            ("expiring", "Expiring Soon"),
            ("expired", "Expired"),
            ("none", "No Expiry"),
        ],
        compute="_compute_expiry",
        store=True,
    )
    notes = fields.Text(groups="faizy_core.group_faizy_ops")
    active = fields.Boolean(default=True)

    @api.depends("expiry_date")
    def _compute_expiry(self):
        today = fields.Date.context_today(self)
        for doc in self:
            if not doc.expiry_date:
                doc.days_to_expiry = 0
                doc.expiry_state = "none"
                continue
            delta = (doc.expiry_date - today).days
            doc.days_to_expiry = delta
            if delta < 0:
                doc.expiry_state = "expired"
            elif delta <= 60:
                doc.expiry_state = "expiring"
            else:
                doc.expiry_state = "valid"

    @api.model
    def _cron_expiry_reminders(self):
        """Warn the customer 60 days out. Renewing a Pakistani passport from
        abroad takes time, so a reminder on the day it expires is useless."""
        soon = self.search([("expiry_state", "=", "expiring")])
        Queue = self.env["faizy.whatsapp.message"].sudo()
        for doc in soon:
            Queue.queue_message(
                partner=doc.partner_id,
                message_type="generic",
                body=self.env._(
                    "Faizy: %(name)s expires on %(date)s (%(days)s days). "
                    "Reply and we will start the renewal.",
                    name=doc.name,
                    date=doc.expiry_date,
                    days=doc.days_to_expiry,
                ),
            )
        return True
