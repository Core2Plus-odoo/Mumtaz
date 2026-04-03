from odoo import fields, models


class MumtazCFOReviewItem(models.Model):
    _name = "mumtaz.cfo.review.item"
    _description = "Mumtaz CFO Review Item"
    _order = "create_date desc"
    _check_company_auto = True

    transaction_id = fields.Many2one("mumtaz.cfo.transaction", required=True, ondelete="cascade", index=True)
    workspace_id = fields.Many2one(related="transaction_id.workspace_id", store=True, index=True, readonly=True)
    company_id = fields.Many2one(related="transaction_id.company_id", store=True, index=True, readonly=True)
    reason = fields.Char(required=True)
    status = fields.Selection(
        [("open", "Open"), ("resolved", "Resolved"), ("ignored", "Ignored")],
        default="open",
        required=True,
        tracking=True,
    )
    notes = fields.Text()

    def action_resolve(self):
        self.write({"status": "resolved"})

    def action_ignore(self):
        self.write({"status": "ignored"})
