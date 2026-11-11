"""Carry the approved-rate price onto a sale line, and freeze it on confirm.

Gold moves every day. A quotation may legitimately be repriced while it is a
draft, but the moment a client agrees to an order the figure they agreed to is
history, not a live calculation. So the price and every component of it are
snapshotted onto the line, and the snapshot is guarded in the ORM once the
order leaves draft — not merely made readonly in a view, which a server action
or an RPC call would walk straight past.

VAT deliberately does NOT come from the pricing engine here. Odoo's own tax
engine owns tax on a sale line, so ``price_unit`` carries the engine's
pre-tax ``subtotal`` and its ``total`` is discarded. Taking VAT from both
would charge it twice.

(The engine is still *called* with the configured VAT rate, because
``get_price_breakdown`` reads it from ``ir.config_parameter``. That is
harmless: ``subtotal`` is the sum of metal, wastage, making and stones and
does not depend on ``vat_rate`` at all. Only ``vat`` and ``total`` do, and
neither is used here.)
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Fields that record what was agreed. Once the order is confirmed these are
# the client's copy of the truth and nothing may rewrite them.
SNAPSHOT_FIELDS = (
    'jewellery_lot_id',
    'jewellery_rate_id',
    'jewellery_rate_per_gram',
    'jewellery_fine_weight_g',
    'jewellery_metal_value',
    'jewellery_wastage_value',
    'jewellery_making_charge',
    'jewellery_stones_value',
    'jewellery_making_discount_pct',
    'jewellery_priced_on',
    'price_unit',
)

# Set by action_price_from_rate so the guard can tell a legitimate pricing run
# from an arbitrary write. Everything else is refused once the order is out of
# draft, including a write made with sudo.
PRICING_CONTEXT = 'jewellery_pricing'

LIVE_STATES = ('sale', 'done')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    jewellery_lot_id = fields.Many2one(
        'stock.lot', string='Piece', copy=False, index=True,
        help='The serial-tracked piece this line sells. Setting it lets the '
             'line be priced from the approved gold rate.')
    jewellery_making_discount_pct = fields.Float(
        string='Making discount %', copy=False,
        help='Trade discount for dealer tiers. It applies to the making '
             'charge only: the metal is never discounted.')

    # --- the snapshot -----------------------------------------------------
    jewellery_rate_id = fields.Many2one(
        'jewellery.gold.rate', string='Rate used', readonly=True, copy=False,
        help='The approved rate this line was priced from.')
    jewellery_rate_per_gram = fields.Float(
        string='Rate per gram', readonly=True, copy=False, digits=(16, 2))
    jewellery_fine_weight_g = fields.Float(
        string='Fine weight (g)', readonly=True, copy=False, digits=(16, 4))
    jewellery_metal_value = fields.Float(
        string='Metal', readonly=True, copy=False, digits=(16, 2))
    jewellery_wastage_value = fields.Float(
        string='Wastage', readonly=True, copy=False, digits=(16, 2))
    jewellery_making_charge = fields.Float(
        string='Making', readonly=True, copy=False, digits=(16, 2))
    jewellery_stones_value = fields.Float(
        string='Stones', readonly=True, copy=False, digits=(16, 2))
    jewellery_priced_on = fields.Datetime(
        string='Priced on', readonly=True, copy=False)

    jewellery_is_priced = fields.Boolean(
        compute='_compute_jewellery_is_priced', store=True,
        help='True once the line carries a rate snapshot.')

    @api.depends('jewellery_rate_id', 'jewellery_priced_on')
    def _compute_jewellery_is_priced(self):
        for line in self:
            line.jewellery_is_priced = bool(
                line.jewellery_rate_id and line.jewellery_priced_on)

    # --- pricing ----------------------------------------------------------
    def action_price_from_rate(self):
        """Price each jewellery line from the rate approved right now.

        Refuses on a confirmed order: repricing something already agreed is
        exactly what the snapshot exists to prevent.
        """
        for line in self:
            if not line.jewellery_lot_id:
                raise UserError(_(
                    'Line "%s" has no piece, so there is nothing to price '
                    'from the gold rate.') % (line.name or line.id))
            if line.order_id.state in LIVE_STATES:
                raise UserError(_(
                    'Order %s is confirmed. Its prices are the ones the '
                    'client agreed to and cannot be recalculated.')
                    % line.order_id.name)

            # price_unit takes breakdown['subtotal'], which is pre-tax and
            # independent of vat_rate. Odoo's tax engine owns the tax.
            breakdown = line.jewellery_lot_id.get_price_breakdown(
                making_discount_pct=line.jewellery_making_discount_pct)

            values = {
                'jewellery_rate_id': breakdown['rate_id'],
                'jewellery_rate_per_gram': breakdown['rate_24k_per_g'],
                'jewellery_fine_weight_g': breakdown['fine_weight_g'],
                'jewellery_metal_value': breakdown['metal_value'],
                'jewellery_wastage_value': breakdown['wastage_value'],
                'jewellery_making_charge': breakdown['making_charge'],
                'jewellery_stones_value': breakdown['stones_value'],
                'jewellery_priced_on': fields.Datetime.now(),
                'price_unit': breakdown['subtotal'],
            }
            line.with_context(**{PRICING_CONTEXT: True}).write(values)
        return True

    # --- the freeze -------------------------------------------------------
    def write(self, values):
        """Refuse to restate a price the client already agreed to.

        Holds for sudo, so a rate feed or a server action cannot quietly
        reprice history either.
        """
        if not self.env.context.get(PRICING_CONTEXT):
            touched = [f for f in SNAPSHOT_FIELDS if f in values]
            if touched:
                for line in self:
                    if (line.jewellery_is_priced
                            and line.order_id.state in LIVE_STATES):
                        raise UserError(_(
                            'Order %(order)s is confirmed. %(fields)s cannot '
                            'be changed: the price and the rate it came from '
                            'are what the client agreed to.',
                            order=line.order_id.name,
                            fields=', '.join(sorted(touched))))
        return super().write(values)

    # --- onward to the invoice -------------------------------------------
    def _prepare_invoice_line(self, **optional_values):
        """Carry the rate snapshot onto the invoice line.

        Standard Odoo already brings `price_unit` across, so the money is
        right without this. What it does not bring is the derivation of that
        money — the approved rate, the fine weight, the split between metal,
        wastage, making and stones. An invoice that cannot show where its
        figure came from is no use in a client query or a margin review.
        """
        values = super()._prepare_invoice_line(**optional_values)
        if self.jewellery_lot_id:
            values.update({
                'jewellery_lot_id': self.jewellery_lot_id.id,
                'jewellery_making_discount_pct':
                    self.jewellery_making_discount_pct,
                'jewellery_rate_id': self.jewellery_rate_id.id,
                'jewellery_rate_per_gram': self.jewellery_rate_per_gram,
                'jewellery_fine_weight_g': self.jewellery_fine_weight_g,
                'jewellery_metal_value': self.jewellery_metal_value,
                'jewellery_wastage_value': self.jewellery_wastage_value,
                'jewellery_making_charge': self.jewellery_making_charge,
                'jewellery_stones_value': self.jewellery_stones_value,
                'jewellery_priced_on': self.jewellery_priced_on,
            })
        return values


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_price_lines_from_rate(self):
        """Price every jewellery line on the order. The form button."""
        lines = self.order_line.filtered('jewellery_lot_id')
        if not lines:
            raise UserError(_('No line on this order carries a piece.'))
        return lines.action_price_from_rate()

    def action_confirm(self):
        """A jewellery line must carry a rate snapshot before it is agreed.

        Without this a piece could be confirmed at whatever price someone
        typed, which is the thing the whole rate discipline exists to stop.
        """
        for order in self:
            unpriced = order.order_line.filtered(
                lambda line: line.jewellery_lot_id
                and not line.jewellery_is_priced)
            if unpriced:
                raise ValidationError(_(
                    'These lines carry a piece but no approved rate: %s.\n'
                    'Price them from the gold rate before confirming.')
                    % ', '.join(
                        line.jewellery_lot_id.name for line in unpriced))
        return super().action_confirm()
