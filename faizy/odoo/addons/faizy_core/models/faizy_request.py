from odoo import api, fields, models
from odoo.exceptions import UserError


class FaizyBridgeRequest(models.Model):
    """A "bridge": the customer needs to talk to someone back home — a doctor,
    a school, an official — with a Faizy facilitating the conversation."""

    _name = "faizy.bridge.request"
    _description = "Faizy Bridge Request"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.bridge")
        or "/",
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, index=True
    )
    family_member_id = fields.Many2one(
        "faizy.family.member", domain="[('partner_id', '=', partner_id)]"
    )
    subject = fields.Char(required=True)
    details = fields.Text()
    counterparty_name = fields.Char()
    counterparty_phone = fields.Char()
    preferred_time = fields.Datetime()
    order_id = fields.Many2one("faizy.order", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )
    outcome_notes = fields.Text()


class FaizyProductRequest(models.Model):
    """Product finder: the customer describes what they want sourced, ops quotes
    it, and only once the customer accepts does it become an order.

    The approval gate is the entire point of this model — never source before
    the customer has agreed a price.
    """

    _name = "faizy.product.request"
    _description = "Faizy Product Request"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.product.request")
        or "/",
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, index=True
    )
    family_member_id = fields.Many2one(
        "faizy.family.member", domain="[('partner_id', '=', partner_id)]"
    )
    product_name = fields.Char(required=True)
    description = fields.Text()
    reference_url = fields.Char(string="Reference Link")
    quantity = fields.Integer(default=1, required=True)

    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    max_budget = fields.Monetary(currency_field="currency_id")
    quoted_price = fields.Monetary(currency_field="currency_id", tracking=True)
    quote_notes = fields.Text()
    quoted_by = fields.Many2one("res.users", readonly=True)
    date_quoted = fields.Datetime(readonly=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("quoted", "Quoted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("completed", "Completed"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    order_id = fields.Many2one("faizy.order", readonly=True, copy=False)

    _sql_quantity_positive = models.Constraint(
        "CHECK (quantity > 0)", "Quantity must be greater than zero."
    )

    def action_send_quote(self):
        for request in self:
            if not request.quoted_price:
                raise UserError(
                    self.env._("Enter a price before quoting %(ref)s.", ref=request.name)
                )
            request.write(
                {
                    "state": "quoted",
                    "quoted_by": self.env.user.id,
                    "date_quoted": fields.Datetime.now(),
                }
            )
            self.env["faizy.whatsapp.message"].sudo().queue_message(
                partner=request.partner_id,
                message_type="generic",
                body=self.env._(
                    "Your Faizy sourcing request %(ref)s is quoted at "
                    "%(price)s. Reply to approve.",
                    ref=request.name,
                    price=request.quoted_price,
                ),
            )

    def action_approve(self):
        """Customer accepted the quote — raise the order that fulfils it."""
        for request in self:
            if request.state != "quoted":
                raise UserError(
                    self.env._("%(ref)s has no quote to approve.", ref=request.name)
                )
            service = self.env.ref(
                "faizy_core.service_product_request", raise_if_not_found=False
            )
            order = self.env["faizy.order"].create(
                {
                    "title": self.env._("Sourcing: %(name)s", name=request.product_name),
                    "description": request.description,
                    "partner_id": request.partner_id.id,
                    "family_member_id": request.family_member_id.id or False,
                    "service_id": service.id if service else False,
                    "city": request.family_member_id.city or request.partner_id.city or "",
                    "purchase_value": request.quoted_price,
                    "currency_id": request.currency_id.id,
                }
            )
            request.write({"state": "approved", "order_id": order.id})

    def action_reject(self):
        self.write({"state": "rejected"})

    @api.onchange("quoted_price")
    def _onchange_quoted_price(self):
        if self.max_budget and self.quoted_price > self.max_budget:
            return {
                "warning": {
                    "title": self.env._("Over budget"),
                    "message": self.env._(
                        "The quote exceeds the customer's stated budget of "
                        "%(budget)s. They are likely to decline.",
                        budget=self.max_budget,
                    ),
                }
            }
