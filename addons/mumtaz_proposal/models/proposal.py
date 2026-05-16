import secrets
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MumtazProposal(models.Model):
    _name = "mumtaz.proposal"
    _description = "Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name desc"

    # ── Identity ────────────────────────────────────────────────────────────
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        domain=[("type", "=", "opportunity")],
        tracking=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
        tracking=True,
    )
    team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
    )

    # ── Template ─────────────────────────────────────────────────────────────
    template_id = fields.Many2one(
        "mumtaz.proposal.template",
        string="Proposal Template",
    )

    # ── State ────────────────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("sent", "Sent"),
            ("viewed", "Viewed"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    # ── Dates ────────────────────────────────────────────────────────────────
    date_proposal = fields.Date(
        string="Proposal Date",
        default=fields.Date.today,
    )
    date_valid = fields.Date(string="Valid Until")
    date_sent = fields.Datetime(string="Sent On", readonly=True, copy=False)
    date_accepted = fields.Datetime(string="Accepted On", readonly=True, copy=False)

    # ── Revision ─────────────────────────────────────────────────────────────
    revision = fields.Integer(string="Revision", default=0, copy=False)

    # ── Lines ────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        "mumtaz.proposal.line",
        "proposal_id",
        string="Proposal Lines",
        copy=True,
    )

    # ── Amounts ──────────────────────────────────────────────────────────────
    amount_untaxed = fields.Monetary(
        string="Subtotal",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_tax = fields.Monetary(
        string="Taxes",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    # ── Content ──────────────────────────────────────────────────────────────
    terms_conditions = fields.Html(string="Terms & Conditions")
    internal_notes = fields.Text(string="Internal Notes")

    # ── Portal ───────────────────────────────────────────────────────────────
    access_token = fields.Char(
        string="Access Token",
        default=lambda self: secrets.token_urlsafe(32),
        copy=False,
        readonly=True,
    )

    # ── Related sale orders ───────────────────────────────────────────────────
    sale_order_ids = fields.One2many(
        "sale.order",
        "proposal_id",
        string="Sale Orders",
    )
    sale_order_count = fields.Integer(
        string="Sale Order Count",
        compute="_compute_sale_order_count",
    )

    # ────────────────────────────────────────────────────────────────────────
    # ORM overrides
    # ────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "mumtaz.proposal"
                ) or _("New")
        return super().create(vals_list)

    def copy(self, default=None):
        default = default or {}
        default.update(
            name=_("New"),
            state="draft",
            date_sent=False,
            date_accepted=False,
            access_token=secrets.token_urlsafe(32),
        )
        return super().copy(default)

    # ────────────────────────────────────────────────────────────────────────
    # Compute methods
    # ────────────────────────────────────────────────────────────────────────

    @api.depends("line_ids.price_subtotal", "line_ids.price_tax")
    def _compute_amounts(self):
        for proposal in self:
            proposal.amount_untaxed = sum(proposal.line_ids.mapped("price_subtotal"))
            proposal.amount_tax = sum(proposal.line_ids.mapped("price_tax"))
            proposal.amount_total = proposal.amount_untaxed + proposal.amount_tax

    @api.depends("sale_order_ids")
    def _compute_sale_order_count(self):
        for proposal in self:
            proposal.sale_order_count = len(proposal.sale_order_ids)

    # ────────────────────────────────────────────────────────────────────────
    # Onchange
    # ────────────────────────────────────────────────────────────────────────

    @api.onchange("opportunity_id")
    def _onchange_opportunity_id(self):
        if self.opportunity_id:
            opp = self.opportunity_id
            self.partner_id = opp.partner_id
            self.user_id = opp.user_id or self.env.user
            self.team_id = opp.team_id

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id and self.template_id.terms_conditions:
            self.terms_conditions = self.template_id.terms_conditions

    # ────────────────────────────────────────────────────────────────────────
    # State transition actions
    # ────────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        for proposal in self:
            proposal.state = "confirmed"

    def action_send(self):
        self.ensure_one()
        return {
            "name": _("Send Proposal"),
            "type": "ir.actions.act_window",
            "res_model": "mumtaz.proposal.send",
            "view_mode": "form",
            "target": "new",
            "context": {"default_proposal_id": self.id},
        }

    def action_mark_sent(self):
        for proposal in self:
            proposal.write(
                {"state": "sent", "date_sent": fields.Datetime.now()}
            )

    def action_mark_viewed(self):
        for proposal in self:
            proposal.state = "viewed"

    def action_accept(self):
        for proposal in self:
            proposal.write(
                {"state": "accepted", "date_accepted": fields.Datetime.now()}
            )
            if proposal.opportunity_id:
                proposal.opportunity_id.action_set_won_rainbowman()

    def action_reject(self):
        for proposal in self:
            proposal.state = "rejected"

    def action_cancel(self):
        for proposal in self:
            proposal.state = "cancelled"

    def action_reset_draft(self):
        for proposal in self:
            proposal.write({"state": "draft", "revision": proposal.revision + 1})

    def action_new_revision(self):
        self.ensure_one()
        new_proposal = self.copy(
            {
                "revision": self.revision + 1,
                "name": _("New"),
            }
        )
        self.state = "cancelled"
        return {
            "name": _("Proposal"),
            "type": "ir.actions.act_window",
            "res_model": "mumtaz.proposal",
            "view_mode": "form",
            "res_id": new_proposal.id,
        }

    # ────────────────────────────────────────────────────────────────────────
    # Sale order creation
    # ────────────────────────────────────────────────────────────────────────

    def action_create_sale_order(self):
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        so_vals = {
            "partner_id": self.partner_id.id,
            "user_id": self.user_id.id,
            "team_id": self.team_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "proposal_id": self.id,
        }
        if self.opportunity_id:
            so_vals["opportunity_id"] = self.opportunity_id.id
        order_lines = []
        for line in self.line_ids:
            so_line_vals = {
                "product_id": line.product_id.id if line.product_id else False,
                "name": line.name,
                "product_uom_qty": line.quantity,
                "price_unit": line.price_unit,
                "discount": line.discount,
            }
            if line.product_uom_id:
                so_line_vals["product_uom"] = line.product_uom_id.id
            if line.tax_ids:
                so_line_vals["tax_id"] = [(6, 0, line.tax_ids.ids)]
            order_lines.append((0, 0, so_line_vals))
        so_vals["order_line"] = order_lines
        sale_order = SaleOrder.create(so_vals)
        return {
            "name": _("Sale Order"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": sale_order.id,
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            "name": _("Sale Orders"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("proposal_id", "=", self.id)],
        }

    # ────────────────────────────────────────────────────────────────────────
    # Template application
    # ────────────────────────────────────────────────────────────────────────

    def action_apply_template(self):
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("Please select a template first."))
        self.line_ids.unlink()
        lines = []
        for tline in self.template_id.line_ids:
            lines.append(
                (
                    0,
                    0,
                    {
                        "sequence": tline.sequence,
                        "product_id": tline.product_id.id if tline.product_id else False,
                        "name": tline.name,
                        "quantity": tline.quantity,
                        "price_unit": tline.price_unit,
                        "discount": tline.discount,
                    },
                )
            )
        self.line_ids = lines
        if self.template_id.terms_conditions:
            self.terms_conditions = self.template_id.terms_conditions

    # ────────────────────────────────────────────────────────────────────────
    # Cron: expire proposals
    # ────────────────────────────────────────────────────────────────────────

    @api.model
    def _check_validity(self):
        today = fields.Date.today()
        expired_proposals = self.search(
            [
                ("date_valid", "<", today),
                ("state", "in", ["confirmed", "sent", "viewed"]),
            ]
        )
        expired_proposals.write({"state": "expired"})
