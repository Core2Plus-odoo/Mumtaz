from odoo import fields, models


class MumtazCFOTransaction(models.Model):
    _name = "mumtaz.cfo.transaction"
    _description = "Mumtaz CFO Transaction"
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    workspace_id = fields.Many2one("mumtaz.cfo.workspace", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="workspace_id.company_id", store=True, index=True, readonly=True)
    batch_id = fields.Many2one("mumtaz.cfo.upload.batch", required=True, index=True, ondelete="restrict")
    data_source_id = fields.Many2one("mumtaz.cfo.data.source", required=True, index=True, ondelete="restrict")

    date = fields.Date(required=True, index=True)
    description = fields.Char(required=True)
    reference = fields.Char()
    amount = fields.Monetary(currency_field="currency_id", required=True)
    currency_id = fields.Many2one("res.currency", required=True)

    direction = fields.Selection(
        [("inflow", "Inflow"), ("outflow", "Outflow")],
        required=True,
        index=True,
    )
    entry_type = fields.Selection(
        [
            ("income", "Income"),
            ("expense", "Expense"),
            ("transfer", "Transfer"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
        index=True,
    )
    category_id = fields.Many2one(
        "mumtaz.cfo.category",
        ondelete="set null",
        domain="[('workspace_id', '=', workspace_id)]",
    )

    source_row_hash = fields.Char(required=True, index=True)
    raw_payload_json = fields.Text()
    is_duplicate = fields.Boolean(default=False, index=True)
    requires_review = fields.Boolean(default=False, index=True)
    review_reason = fields.Char()
    review_item_id = fields.Many2one("mumtaz.cfo.review.item", readonly=True, copy=False)

    _sql_constraints = [
        (
            "mumtaz_cfo_transaction_batch_hash_unique",
            "unique(batch_id, source_row_hash)",
            "A source row can only be imported once per batch.",
        )
    ]

    @fields.depends("date", "description", "amount")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.date or ''} | {rec.description or ''} | {rec.amount or 0:.2f}"
