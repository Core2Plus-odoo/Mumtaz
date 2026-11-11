"""Carry the rate snapshot onto the invoice, and freeze it once posted.

Standard Odoo already carries the *money*: `_prepare_invoice_line` copies
`price_unit` from the sale line, so the figure on the invoice is the figure
that was agreed. What it does not carry is the **evidence** — which approved
rate that money came from, the fine weight it was computed on, and how it
split between metal, wastage, making and stones. Without that, an invoice is
a number with no derivation, which is exactly what a client query, a margin
review or an audit needs.

So the snapshot travels with the line, and then stops moving.

Two things are worth stating plainly, because both were checked against the
Odoo 19 source rather than assumed:

**Odoo does not protect `price_unit` on a posted line by default.**
`account.move.line.write` blocks edits to a posted line only through the
fiscal lock date, the tax lock date, or an inalterable hash. With none of
those configured — which is the state of a fresh database — the price on a
posted invoice line can be rewritten. For a line that carries a piece, that
price is what a client agreed to pay for a specific object, so this module
refuses it outright.

**The snapshot fields are `copy=True`, unlike their sale-line counterparts.**
On a sale line a copy is a new negotiation and must be priced afresh. An
invoice is the opposite: a credit note is produced by reversing the move, and
a credit note that lost the derivation of the amount it reverses would be
worse than useless. So the evidence is carried, and the posted-state guard is
what keeps it honest.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# What was agreed, and the derivation of it. Once the move is posted these are
# the client's copy of the truth.
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


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    jewellery_lot_id = fields.Many2one(
        'stock.lot', string='Piece', index=True,
        help='The serial-tracked piece this line invoices.')
    jewellery_making_discount_pct = fields.Float(
        string='Making discount %',
        help='Trade discount applied to the making charge only. The metal is '
             'never discounted.')

    # --- the snapshot, carried from the sale line ---------------------------
    jewellery_rate_id = fields.Many2one(
        'jewellery.gold.rate', string='Rate used', readonly=True,
        help='The approved rate this line was priced from.')
    jewellery_rate_per_gram = fields.Float(
        string='Rate per gram', readonly=True, digits=(16, 2))
    jewellery_fine_weight_g = fields.Float(
        string='Fine weight (g)', readonly=True, digits=(16, 4))
    jewellery_metal_value = fields.Float(
        string='Metal', readonly=True, digits=(16, 2))
    jewellery_wastage_value = fields.Float(
        string='Wastage', readonly=True, digits=(16, 2))
    jewellery_making_charge = fields.Float(
        string='Making', readonly=True, digits=(16, 2))
    jewellery_stones_value = fields.Float(
        string='Stones', readonly=True, digits=(16, 2))
    jewellery_priced_on = fields.Datetime(
        string='Priced on', readonly=True)

    jewellery_is_priced = fields.Boolean(
        compute='_compute_jewellery_is_priced', store=True,
        help='True once the line carries a rate snapshot.')

    @api.depends('jewellery_rate_id', 'jewellery_priced_on')
    def _compute_jewellery_is_priced(self):
        for line in self:
            line.jewellery_is_priced = bool(
                line.jewellery_rate_id and line.jewellery_priced_on)

    # --- the freeze --------------------------------------------------------
    def write(self, values):
        """Refuse to restate a posted jewellery line.

        Holds for sudo: the likeliest thing to rewrite an old invoice is an
        automated correction or a rate feed, not a person in a form.
        """
        touched = [f for f in SNAPSHOT_FIELDS if f in values]
        if touched:
            for line in self:
                # move_id.state, not the stored related parent_state, which
                # can lag inside a transaction that is posting the move.
                if (line.jewellery_lot_id
                        and line.move_id.state == 'posted'):
                    raise UserError(_(
                        '%(move)s is posted. %(fields)s cannot be changed: '
                        'the price and the gold rate it came from are what '
                        'the client was invoiced.',
                        move=line.move_id.name or _('This entry'),
                        fields=', '.join(sorted(touched))))
        return super().write(values)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        """An invoiced piece must carry the rate it was priced from.

        Guarding `_post` rather than `action_post` covers the automated paths
        too — a payment-term flow or a scheduled action posts through here.
        """
        for move in self:
            unpriced = move.line_ids.filtered(
                lambda line: line.jewellery_lot_id
                and not line.jewellery_is_priced)
            if unpriced:
                raise ValidationError(_(
                    'These lines carry a piece but no approved gold rate: '
                    '%s.\nAn invoice for a piece must record the rate it was '
                    'priced from.')
                    % ', '.join(
                        line.jewellery_lot_id.name for line in unpriced))
        return super()._post(soft=soft)
