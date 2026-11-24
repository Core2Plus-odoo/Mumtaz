import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FaizyOrderCustomerBilling(models.Model):
    """Invoice the customer, and record it on their wallet, when an order
    completes.

    Closes the sibling to the vendor-bill gap: `amount_total` (purchase_value
    + platform_fee + service_fee) has always been computed and shown on the
    order and sent to the customer as a WhatsApp receipt
    (`faizy_whatsapp.py._render_body`'s "receipt" branch), but nothing ever
    turned it into an actual AR fact. `faizy_product_data.xml` already
    prepared `product_platform_fee`/`product_service_fee` for exactly this,
    noting "orders do not reach accounting at all today."

    Two records, by design, not one standing in for the other:
    - `account.move` (out_invoice) is the real accounting fact — AR, GL, tax.
      Drafted, never posted, same convention as the vendor bill and
      subscription invoices: a person reviews and posts.
    - `faizy.wallet.transaction` is NOT accounting — see its own model
      docstring and faizy/docs/architecture/ENTITY_RELATIONSHIPS.md. It is
      the running-balance figure the customer portal already displays
      (`res_partner.py.wallet_balance`), logged here purely so that display
      stops being permanently zero for every customer who has ever had a
      completed order.
    """

    _inherit = "faizy.order"

    customer_invoice_id = fields.Many2one(
        "account.move",
        readonly=True,
        copy=False,
        help="Draft customer Invoice for this order's total "
        "(purchase value + platform fee + service fee). Created once, on "
        "completion.",
    )

    def action_complete(self):
        super().action_complete()
        for order in self:
            if order.is_sample or order.customer_invoice_id:
                continue
            if order.amount_total > 0:
                try:
                    order._create_customer_invoice()
                except Exception:
                    # Same rule as faizy_order_alert.py and the vendor bill:
                    # a bookkeeping side effect failing must never undo the
                    # real-world fact that the job is done.
                    _logger.exception(
                        "Faizy customer invoice draft failed for order %s",
                        order.id,
                    )

    def action_create_customer_invoice(self):
        """Manual retry — for when the automatic draft on completion failed
        (e.g. a missing exchange rate)."""
        for order in self:
            if order.customer_invoice_id:
                raise UserError(self.env._(
                    "%(ref)s already has a customer invoice (%(inv)s).",
                    ref=order.name, inv=order.customer_invoice_id.display_name,
                ))
            if order.amount_total <= 0:
                raise UserError(self.env._(
                    "%(ref)s has nothing to invoice (total is %(total)s).",
                    ref=order.name, total=order.amount_total,
                ))
            order._create_customer_invoice()

    def action_view_customer_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Customer Invoice"),
            "res_model": "account.move",
            "res_id": self.customer_invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _check_customer_invoice_exchange_rate(self):
        """Same guard, and the same reason, as
        faizy.subscription._check_exchange_rate and
        faizy_vendor_billing._check_vendor_bill_exchange_rate: a currency
        with no rate row would post 1:1 against the company currency with
        nothing warning that it happened."""
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
                    "%(order)s would invoice the customer in %(cur)s but the "
                    "books are in %(company)s, and no %(cur)s exchange rate "
                    "exists. Set one in Accounting -> Configuration -> "
                    "Currencies -> %(cur)s, then create the invoice again.",
                    order=self.name,
                    cur=self.currency_id.name,
                    company=company.currency_id.name,
                )
            )

    def _customer_invoice_lines(self):
        self.ensure_one()
        lines = []
        if self.purchase_value:
            lines.append((0, 0, {
                "product_id": self.env.ref(
                    "faizy_core.product_purchase_reimbursement"
                ).id,
                "name": self.env._(
                    "%(ref)s — %(title)s", ref=self.name, title=self.title or ""
                ),
                "quantity": 1,
                "price_unit": self.purchase_value,
            }))
        if self.platform_fee:
            lines.append((0, 0, {
                "product_id": self.env.ref("faizy_core.product_platform_fee").id,
                "name": self.env._("Platform fee on %(ref)s", ref=self.name),
                "quantity": 1,
                "price_unit": self.platform_fee,
            }))
        if self.service_fee:
            lines.append((0, 0, {
                "product_id": self.env.ref("faizy_core.product_service_fee").id,
                "name": self.env._("Service fee on %(ref)s", ref=self.name),
                "quantity": 1,
                "price_unit": self.service_fee,
            }))
        return lines

    def _create_customer_invoice(self):
        """Draft the Invoice, then log the matching wallet debit. Never
        posts the invoice — a person reviews and posts."""
        self.ensure_one()
        self._check_customer_invoice_exchange_rate()

        # sudo(): completion is done by Operations (HQ05: Raza), who has no
        # Accounting rights and must not get them. The draft is a system side
        # effect of the completion; posting it stays with a person who has
        # Accounting access. Without this the draft silently failed for every
        # non-accountant who completed an order.
        invoice = self.env["account.move"].sudo().create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id,
            "invoice_origin": self.name,
            "invoice_line_ids": self._customer_invoice_lines(),
        })
        self.customer_invoice_id = invoice

        # Informational only — see the class docstring. Logged after the
        # invoice exists so the wallet row's reference always points at a
        # real document, never at one that failed to create.
        self.env["faizy.wallet.transaction"].sudo().create({
            "partner_id": self.partner_id.id,
            "order_id": self.id,
            "txn_type": "debit",
            "amount": -self.amount_total,
            "currency_id": self.currency_id.id,
            "reference": invoice.display_name,
            "note": self.env._(
                "%(ref)s completed — invoiced %(amount)s %(currency)s.",
                ref=self.name,
                amount=f"{self.amount_total:.2f}",
                currency=self.currency_id.name,
            ),
        })

        self.message_post(body=self.env._(
            "Draft customer invoice %(inv)s created for %(total)s "
            "%(currency)s. Review and post it in Accounting.",
            inv=invoice.display_name,
            total=f"{self.amount_total:.2f}",
            currency=self.currency_id.name,
        ))
        return invoice
