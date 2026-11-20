import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FaizyOrderVendorBilling(models.Model):
    """Draft a Vendor Bill when a vendor-fulfilled order completes.

    Closes a real, documented gap: `vendor_commission` has always been
    computed and shown (see `faizy_order.py._compute_amounts` and
    `faizy_vendor.py`'s own docstring — "vendor bills, payments and the
    accounting side of a commission" already point at this contact) but
    nothing ever turned it into an actual payable. A human has had to create
    the Vendor Bill by hand every time. See
    faizy/docs/project/FIT_GAP_REGISTER.md, row FIN-03.

    Drafted, never posted — mirrors `faizy.subscription._generate_invoice`'s
    own convention for customer invoices. An accountant reviews and posts;
    this code only makes sure the bill exists and is correct, not that it is
    final.
    """

    _inherit = "faizy.order"

    vendor_bill_id = fields.Many2one(
        "account.move",
        readonly=True,
        copy=False,
        help="Draft Vendor Bill for what Faizy owes the vendor, net of the "
        "commission Faizy retains. Created once, on completion.",
    )

    def action_complete(self):
        super().action_complete()
        for order in self:
            if order.is_sample or order.vendor_bill_id:
                continue
            if order.vendor_id and order.purchase_value > 0:
                try:
                    order._create_vendor_bill()
                except Exception:
                    # Mirrors faizy_order_alert.py's own rule: a bookkeeping
                    # side effect failing must never undo the real-world fact
                    # that the job is done. The order stays completed; the
                    # bill stays missing and retryable via the button below.
                    _logger.exception(
                        "Faizy vendor bill draft failed for order %s", order.id
                    )

    def action_create_vendor_bill(self):
        """Manual retry — for when the automatic draft on completion failed
        (e.g. a missing exchange rate) and ops needs to try again without
        waiting for a developer."""
        for order in self:
            if not order.vendor_id:
                raise UserError(_("%(ref)s has no vendor to bill.", ref=order.name))
            if order.vendor_bill_id:
                raise UserError(_(
                    "%(ref)s already has a vendor bill (%(bill)s).",
                    ref=order.name, bill=order.vendor_bill_id.display_name,
                ))
            order._create_vendor_bill()

    def action_view_vendor_bill(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Vendor Bill"),
            "res_model": "account.move",
            "res_id": self.vendor_bill_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _check_vendor_bill_exchange_rate(self):
        """Same guard, and the same reason, as
        faizy.subscription._check_exchange_rate: a vendor billed in a
        currency with no rate row would post 1:1 against the company
        currency with nothing warning that it happened."""
        self.ensure_one()
        company = self.env.company
        if self.currency_id == company.currency_id:
            return
        has_rate = self.env["res.currency.rate"].sudo().search_count(
            [
                ("currency_id", "=", self.currency_id.id),
                ("company_id", "in", (False, company.id)),
            ],
            limit=1,
        )
        if not has_rate:
            raise UserError(
                self.env._(
                    "%(order)s would bill its vendor in %(cur)s but the books "
                    "are in %(company)s, and no %(cur)s exchange rate exists. "
                    "Set one in Accounting -> Configuration -> Currencies -> "
                    "%(cur)s, then create the vendor bill again.",
                    order=self.name,
                    cur=self.currency_id.name,
                    company=company.currency_id.name,
                )
            )

    def _create_vendor_bill(self):
        """Draft the Vendor Bill. Never posts it — a person reviews and posts.

        Two lines rather than one net figure: the gross amount procured and
        the commission Faizy retains both stay visible and auditable on the
        bill itself, not folded into a number nobody can check.
        """
        self.ensure_one()
        self._check_vendor_bill_exchange_rate()

        lines = [
            (0, 0, {
                "product_id": self.env.ref("faizy_core.product_vendor_procurement").id,
                "name": self.env._(
                    "%(ref)s — %(title)s", ref=self.name, title=self.title or ""
                ),
                "quantity": 1,
                "price_unit": self.purchase_value,
            })
        ]
        if self.vendor_commission:
            lines.append((0, 0, {
                "product_id": self.env.ref(
                    "faizy_core.product_vendor_commission_retained"
                ).id,
                "name": self.env._(
                    "Commission retained on %(ref)s", ref=self.name
                ),
                "quantity": 1,
                "price_unit": -self.vendor_commission,
            }))

        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.vendor_id.id,
            "invoice_date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id,
            "invoice_origin": self.name,
            "invoice_line_ids": lines,
        })
        self.vendor_bill_id = bill
        self.message_post(body=self.env._(
            "Draft vendor bill %(bill)s created: %(gross)s procured, "
            "%(commission)s retained, %(net)s payable. Review and post it "
            "in Accounting.",
            bill=bill.display_name,
            gross=f"{self.purchase_value:.2f}",
            commission=f"{self.vendor_commission:.2f}",
            net=f"{self.purchase_value - self.vendor_commission:.2f}",
        ))
        return bill
