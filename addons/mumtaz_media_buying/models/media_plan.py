# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .media_outlet import MEDIA_CHANNELS

PLAN_STATES = [
    ("draft", "Draft"),
    ("approved", "Approved"),
    ("running", "In Flight"),
    ("done", "Completed"),
    ("cancelled", "Cancelled"),
]


class MediaPlan(models.Model):
    """The campaign blueprint for a client: what is bought, where, for how
    much — plus the agency's commission and fees. Once approved it generates
    the client sale order and per-vendor purchase orders (no double entry)."""

    _name = "media.plan"
    _description = "Media Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True,
        default=lambda self: self.env._("New"),
    )
    campaign = fields.Char(
        string="Campaign", required=True, tracking=True,
        help="Campaign name as the client knows it, e.g. 'Summer Refresh 2026'.",
    )
    client_id = fields.Many2one(
        "res.partner", string="Client", required=True, tracking=True,
        domain=[("is_media_vendor", "=", False)],
    )
    user_id = fields.Many2one(
        "res.users", string="Account Manager",
        default=lambda self: self.env.user, tracking=True,
    )
    date_from = fields.Date(string="Start", required=True, tracking=True)
    date_to = fields.Date(string="End", required=True, tracking=True)
    state = fields.Selection(
        PLAN_STATES, default="draft", required=True, tracking=True, copy=False
    )
    currency_id = fields.Many2one(
        "res.currency", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )

    budget = fields.Monetary(
        currency_field="currency_id", tracking=True,
        help="Client-approved budget envelope for this campaign "
             "(media + commission + fees).",
    )
    commission_percent = fields.Float(
        string="Commission (%)", default=15.0, tracking=True,
        help="Agency commission applied on top of net media cost.",
    )
    service_fee = fields.Monetary(
        currency_field="currency_id", tracking=True,
        help="Flat service / management fee for this campaign.",
    )

    line_ids = fields.One2many("media.plan.line", "plan_id", string="Placements",
                               copy=True)
    notes = fields.Text()

    # -- computed commercials ------------------------------------------------
    media_cost = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="Total net cost payable to vendors.",
    )
    commission_amount = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True
    )
    client_total = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="Total billed to the client: media + commission + service fee.",
    )
    net_revenue = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="Agency earnings: commission + service fee.",
    )
    margin_percent = fields.Float(
        string="Margin (%)", compute="_compute_amounts", store=True
    )

    # -- generated documents -------------------------------------------------
    sale_order_id = fields.Many2one("sale.order", string="Client Order",
                                    copy=False, readonly=True)
    purchase_order_ids = fields.Many2many(
        "purchase.order", string="Vendor Orders", copy=False, readonly=True
    )
    purchase_order_count = fields.Integer(
        compute="_compute_order_counts"
    )
    sale_order_count = fields.Integer(compute="_compute_order_counts")

    @api.depends("line_ids.net_cost", "line_ids.client_amount",
                 "commission_percent", "service_fee")
    def _compute_amounts(self):
        for plan in self:
            media = sum(plan.line_ids.mapped("net_cost"))
            client_lines = sum(plan.line_ids.mapped("client_amount"))
            plan.media_cost = media
            plan.commission_amount = client_lines - media
            plan.client_total = client_lines + plan.service_fee
            plan.net_revenue = plan.commission_amount + plan.service_fee
            plan.margin_percent = (
                plan.net_revenue / plan.client_total * 100.0
                if plan.client_total else 0.0
            )

    def _compute_order_counts(self):
        for plan in self:
            plan.sale_order_count = 1 if plan.sale_order_id else 0
            plan.purchase_order_count = len(plan.purchase_order_ids)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for plan in self:
            if plan.date_to < plan.date_from:
                raise ValidationError(
                    self.env._("The campaign end date must be after its start."))

    @api.constrains("commission_percent")
    def _check_commission(self):
        for plan in self:
            if plan.commission_percent < 0:
                raise ValidationError(
                    self.env._("Commission cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("media.plan")
                    or self.env._("New")
                )
        return super().create(vals_list)

    # -- workflow ------------------------------------------------------------
    def action_approve(self):
        for plan in self:
            if not plan.line_ids:
                raise UserError(self.env._(
                    "Add at least one placement before approving the plan."))
        self.write({"state": "approved"})

    def action_start(self):
        self.write({"state": "running"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})

    # -- document generation ---------------------------------------------
    def _get_media_product(self):
        product = self.env.ref(
            "mumtaz_media_buying.product_media_placement",
            raise_if_not_found=False,
        )
        if not product:
            raise UserError(self.env._(
                "The 'Media Placement' service product is missing. "
                "Reinstall or upgrade the Media Buying module."))
        return product

    def action_create_orders(self):
        """Generate the client sale order and one purchase order per vendor
        from the plan lines. Idempotent: existing documents are kept."""
        self.ensure_one()
        if self.state not in ("approved", "running"):
            raise UserError(self.env._(
                "Approve the media plan before generating orders."))
        product = self._get_media_product()

        # Client sale order: media at client price + service fee line.
        if not self.sale_order_id:
            so_lines = []
            for line in self.line_ids:
                qty = line.qty or 1.0
                so_lines.append((0, 0, {
                    "product_id": product.id,
                    "name": line._order_description(),
                    "product_uom_qty": qty,
                    "price_unit": line.client_amount / qty,
                }))
            if self.service_fee:
                so_lines.append((0, 0, {
                    "product_id": product.id,
                    "name": self.env._("Agency service fee — %s") % self.campaign,
                    "product_uom_qty": 1.0,
                    "price_unit": self.service_fee,
                }))
            self.sale_order_id = self.env["sale.order"].create({
                "partner_id": self.client_id.id,
                "origin": self.name,
                "order_line": so_lines,
            })

        # One PO per vendor at negotiated cost.
        existing_vendors = self.purchase_order_ids.mapped("partner_id")
        new_pos = self.env["purchase.order"]
        for vendor in self.line_ids.mapped("outlet_id.vendor_id"):
            if vendor in existing_vendors:
                continue
            lines = self.line_ids.filtered(
                lambda l, v=vendor: l.outlet_id.vendor_id == v)
            po_lines = []
            for line in lines:
                qty = line.qty or 1.0
                po_lines.append((0, 0, {
                    "product_id": product.id,
                    "name": line._order_description(),
                    "product_qty": qty,
                    "price_unit": line.net_cost / qty,
                    "date_planned": fields.Datetime.now(),
                }))
            new_pos |= self.env["purchase.order"].create({
                "partner_id": vendor.id,
                "origin": self.name,
                "order_line": po_lines,
            })
        if new_pos:
            self.purchase_order_ids = [(4, po.id) for po in new_pos]
        return True

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.purchase_order_ids.ids)],
            "name": self.env._("Vendor Orders"),
        }


class MediaPlanLine(models.Model):
    """One placement in a media plan: an outlet/format, quantity and rate.
    Costs price from the rate card; the client amount adds the plan's
    commission."""

    _name = "media.plan.line"
    _description = "Media Plan Line"
    _order = "plan_id, channel, id"

    plan_id = fields.Many2one(
        "media.plan", required=True, ondelete="cascade", index=True
    )
    outlet_id = fields.Many2one("media.outlet", required=True)
    channel = fields.Selection(
        MEDIA_CHANNELS, related="outlet_id.channel", store=True
    )
    vendor_id = fields.Many2one(
        related="outlet_id.vendor_id", store=True, string="Vendor"
    )
    rate_line_id = fields.Many2one(
        "media.rate.card.line",
        string="Rate Card Line",
        domain="[('outlet_id', '=', outlet_id), ('state', '=', 'active')]",
        help="Pick an active negotiated rate; quantity × rate prices the line.",
    )
    description = fields.Char(
        help="What is bought, e.g. '30-sec prime-time spot'. Defaults from "
             "the rate card line.",
    )
    qty = fields.Float(string="Quantity", default=1.0, required=True)
    unit_rate = fields.Monetary(
        currency_field="currency_id", required=True,
        help="Net cost per unit payable to the vendor.",
    )
    discount = fields.Float(
        string="Discount (%)", default=0.0,
        help="Extra negotiated discount on this line.",
    )
    currency_id = fields.Many2one(related="plan_id.currency_id")
    net_cost = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="qty × rate × (1 − discount): what the agency pays the vendor.",
    )
    client_amount = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="Net cost plus the plan's commission: what the client is billed.",
    )

    @api.depends("qty", "unit_rate", "discount",
                 "plan_id.commission_percent")
    def _compute_amounts(self):
        for line in self:
            net = line.qty * line.unit_rate * (1 - line.discount / 100.0)
            line.net_cost = net
            line.client_amount = net * (
                1 + (line.plan_id.commission_percent or 0.0) / 100.0)

    @api.onchange("rate_line_id")
    def _onchange_rate_line_id(self):
        if self.rate_line_id:
            self.unit_rate = self.rate_line_id.rate
            if not self.description:
                self.description = self.rate_line_id.name

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        if (self.rate_line_id
                and self.rate_line_id.outlet_id != self.outlet_id):
            self.rate_line_id = False

    def _order_description(self):
        """Line description used on generated sale / purchase orders."""
        self.ensure_one()
        parts = [self.plan_id.campaign, self.outlet_id.name]
        if self.description:
            parts.append(self.description)
        return " — ".join(p for p in parts if p)
