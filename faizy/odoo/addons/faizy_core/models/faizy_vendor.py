from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FaizyVendorPartner(models.Model):
    """The vendor segment: shops, pharmacies, labs and couriers we buy from.

    A segment on res.partner, not a `faizy.vendor` model. `faizy.order.vendor_id`
    already points at res.partner, and so do vendor bills, payments and the
    accounting side of a commission — inventing a parallel vendor table would
    mean the same counterparty exists twice, and the day the two disagree
    nobody can say which one is right. That is the mistake this codebase avoids
    everywhere else (customers are res.partner too), so vendors follow it.

    What a vendor *is*, operationally: a third party who fulfils part of an
    order. We charge the customer the purchase value plus the platform fee, and
    we retain a commission from the vendor — revenue to Faizy that the customer
    never sees on their invoice.
    """

    _inherit = "res.partner"

    is_faizy_vendor = fields.Boolean(
        string="Faizy Vendor",
        index=True,
        copy=False,
        help="Fulfils Faizy orders. Shows up in Faizy → Network → Vendors.",
    )
    faizy_vendor_code = fields.Char(
        string="Vendor Code",
        readonly=True,
        copy=False,
        index=True,
        help="FZV-xxxxx. Quoted on bills and in WhatsApp so ops and the vendor "
        "are talking about the same record.",
    )

    faizy_vendor_type = fields.Selection(
        [
            ("pharmacy", "Pharmacy"),
            ("grocery", "Grocery / Kiryana"),
            ("clinic", "Clinic / Doctor"),
            ("lab", "Diagnostic Lab"),
            ("courier", "Courier / Transport"),
            ("utility", "Utility / Bill Agent"),
            ("repair", "Repair / Home Services"),
            ("other", "Other"),
        ],
        string="Vendor Type",
        index=True,
    )
    faizy_vendor_state = fields.Selection(
        [
            ("prospect", "Prospect"),
            ("active", "Active"),
            ("suspended", "Suspended"),
        ],
        string="Vendor Status",
        default="prospect",
        index=True,
        tracking=True,
        help="Only active vendors should be assigned new orders.",
    )
    faizy_vendor_onboarded = fields.Date(string="Onboarded On", copy=False)

    faizy_vendor_area_ids = fields.Many2many(
        "faizy.area",
        "faizy_vendor_area_rel",
        "partner_id",
        "area_id",
        string="Areas Covered",
    )
    faizy_vendor_service_ids = fields.Many2many(
        "faizy.service",
        "faizy_vendor_service_rel",
        "partner_id",
        "service_id",
        string="Services Fulfilled",
    )
    faizy_vendor_note = fields.Text(
        string="Vendor Notes",
        help="Delivery windows, who to ask for, what they are good at.",
    )

    # ── Commission ───────────────────────────────────────────────────────
    # The company rate is the default; this is the exception. A boolean rather
    # than "0.0 means inherit", because 0% is a real commercial arrangement —
    # a partner clinic we take nothing from — and it must be expressible.
    faizy_vendor_custom_commission = fields.Boolean(
        string="Custom Commission",
        help="Off: this vendor uses the company rate in Settings.",
    )
    faizy_vendor_commission_rate = fields.Float(
        string="Commission Rate",
        digits=(3, 4),
        help="Retained from this vendor. 0.10 = 10%.",
    )
    faizy_vendor_effective_rate = fields.Float(
        string="Effective Rate",
        compute="_compute_faizy_vendor_effective_rate",
        digits=(3, 4),
        help="What the next order will actually use.",
    )

    # ── Performance ──────────────────────────────────────────────────────
    faizy_vendor_order_ids = fields.One2many(
        "faizy.order", "vendor_id", string="Fulfilled Orders"
    )
    faizy_vendor_order_count = fields.Integer(
        string="Orders", compute="_compute_faizy_vendor_stats"
    )
    faizy_vendor_purchase_value = fields.Monetary(
        string="Purchase Value",
        compute="_compute_faizy_vendor_stats",
        currency_field="currency_id",
        help="Everything bought through this vendor on completed orders.",
    )
    faizy_vendor_commission_total = fields.Monetary(
        string="Commission Earned",
        compute="_compute_faizy_vendor_stats",
        currency_field="currency_id",
    )
    faizy_vendor_last_order = fields.Datetime(
        string="Last Order", compute="_compute_faizy_vendor_stats"
    )

    @api.depends("faizy_vendor_custom_commission", "faizy_vendor_commission_rate")
    def _compute_faizy_vendor_effective_rate(self):
        company_rate = self.env.company.faizy_vendor_commission_rate
        for partner in self:
            partner.faizy_vendor_effective_rate = (
                partner.faizy_vendor_commission_rate
                if partner.faizy_vendor_custom_commission
                else company_rate
            )

    def _compute_faizy_vendor_stats(self):
        """Completed orders only — a pending order is not turnover yet.

        Aggregated in one grouped read rather than by walking the one2many, so
        a vendor with three years of orders does not load them all to show a
        number in a stat button.
        """
        blank = {"count": 0, "purchase": 0.0, "commission": 0.0, "last": False}
        totals = dict.fromkeys(self.ids, None)

        grouped = self.env["faizy.order"]._read_group(
            [("vendor_id", "in", self.ids), ("state", "=", "completed")],
            groupby=["vendor_id"],
            aggregates=[
                "__count",
                "purchase_value:sum",
                "vendor_commission:sum",
                "date_completed:max",
            ],
        )
        for vendor, count, purchase, commission, last in grouped:
            totals[vendor.id] = {
                "count": count,
                "purchase": purchase or 0.0,
                "commission": commission or 0.0,
                "last": last,
            }

        for partner in self:
            values = totals.get(partner.id) or blank
            partner.faizy_vendor_order_count = values["count"]
            partner.faizy_vendor_purchase_value = values["purchase"]
            partner.faizy_vendor_commission_total = values["commission"]
            partner.faizy_vendor_last_order = values["last"]

    @api.constrains("faizy_vendor_commission_rate", "faizy_vendor_custom_commission")
    def _check_faizy_vendor_commission_rate(self):
        for partner in self:
            if not partner.faizy_vendor_custom_commission:
                continue
            if not 0.0 <= partner.faizy_vendor_commission_rate <= 1.0:
                raise ValidationError(
                    self.env._(
                        "A commission rate is a share, so it belongs between 0 "
                        "and 1 — 0.10 for 10%%. Got %(rate)s.",
                        rate=partner.faizy_vendor_commission_rate,
                    )
                )

    # ── Bookkeeping ──────────────────────────────────────────────────────

    def _faizy_vendor_defaults(self, values):
        """Fill in what flagging a partner as a vendor implies.

        `supplier_rank` is the part that matters beyond Faizy: it is what makes
        Odoo offer this contact in vendor bills and payments, so a Faizy vendor
        is a vendor everywhere in the database rather than only in our own
        screens.
        """
        if not values.get("faizy_vendor_code"):
            values["faizy_vendor_code"] = (
                self.env["ir.sequence"].next_by_code("faizy.vendor") or "/"
            )
        return values

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_faizy_vendor"):
                self._faizy_vendor_defaults(vals)
                vals.setdefault("supplier_rank", 1)
        return super().create(vals_list)

    def write(self, vals):
        # Only when the flag is being turned ON, and only for records that were
        # not already vendors — otherwise every save on a vendor would try to
        # pull another sequence number.
        if vals.get("is_faizy_vendor"):
            newly = self.filtered(lambda p: not p.is_faizy_vendor)
            result = super().write(vals)
            for partner in newly:
                stamp = {}
                # A partner who was a vendor before keeps the code they were
                # billed under; pulling a fresh one would orphan their history.
                if not partner.faizy_vendor_code:
                    partner._faizy_vendor_defaults(stamp)
                if not partner.supplier_rank:
                    stamp["supplier_rank"] = 1
                if stamp:
                    super(FaizyVendorPartner, partner).write(stamp)
            return result
        return super().write(vals)

    # ── Actions ──────────────────────────────────────────────────────────

    def action_faizy_vendor_activate(self):
        self.write(
            {
                "faizy_vendor_state": "active",
                "faizy_vendor_onboarded": fields.Date.context_today(self),
            }
        )

    def action_faizy_vendor_suspend(self):
        self.write({"faizy_vendor_state": "suspended"})

    def action_view_faizy_vendor_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Fulfilled Orders"),
            "res_model": "faizy.order",
            "view_mode": "list,form",
            "domain": [("vendor_id", "=", self.id)],
            "context": {"default_vendor_id": self.id},
        }
