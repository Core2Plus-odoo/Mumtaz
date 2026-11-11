from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..services import pricing
from .product import KARATS, MAKING_TYPES


class StockLot(models.Model):
    """A serial-tracked jewellery piece."""

    _inherit = 'stock.lot'

    gross_weight_g = fields.Float(string='Gross weight (g)', digits=(16, 3))
    stone_weight_g = fields.Float(string='Stone weight (g)', digits=(16, 3))
    net_weight_g = fields.Float(
        string='Net metal weight (g)', digits=(16, 3),
        compute='_compute_net_weight', store=True)
    karat = fields.Selection(
        KARATS, compute='_compute_defaults', store=True, readonly=False)
    wastage_pct = fields.Float(
        string='Wastage %', compute='_compute_defaults', store=True,
        readonly=False)
    making_type = fields.Selection(
        MAKING_TYPES, compute='_compute_defaults', store=True,
        readonly=False)
    making_value = fields.Float(
        compute='_compute_defaults', store=True, readonly=False)
    stones_value = fields.Float(string='Stones value', digits=(16, 2))
    rfid_tag = fields.Char(string='RFID tag', copy=False, index=True)
    certificate_ref = fields.Char(string='Certificate reference')
    jewellery_price = fields.Float(
        string='Price incl. VAT (live rate)', digits=(16, 2),
        compute='_compute_jewellery_price')
    # What the piece actually cost the business: metal bought, making paid,
    # stones bought. Recorded, never derived from the pricing engine, which
    # values at market and says nothing about what was paid (plan §3: "do
    # not derive accounting or inventory figures from the pricing engine").
    # Managers only: a counter screen must not show cost next to price.
    jewellery_cost_value = fields.Float(
        string='Cost basis', digits=(16, 2),
        groups='mumtaz_jewellery.group_jewellery_manager',
        help='Actual cost of this piece (metal, making, stones), recorded '
             'at intake. Margin on a sale is price minus this figure.')

    @api.depends('gross_weight_g', 'stone_weight_g')
    def _compute_net_weight(self):
        for lot in self:
            lot.net_weight_g = max(
                lot.gross_weight_g - lot.stone_weight_g, 0.0)

    @api.depends('product_id')
    def _compute_defaults(self):
        for lot in self:
            tmpl = lot.product_id.product_tmpl_id
            if tmpl.is_jewellery:
                lot.karat = lot.karat or tmpl.jewellery_karat
                lot.wastage_pct = lot.wastage_pct or tmpl.jewellery_wastage_pct
                lot.making_type = lot.making_type or tmpl.jewellery_making_type
                lot.making_value = (
                    lot.making_value or tmpl.jewellery_making_value)

    @api.constrains('stone_weight_g', 'gross_weight_g')
    def _check_weights(self):
        for lot in self:
            if lot.stone_weight_g > lot.gross_weight_g:
                raise ValidationError(
                    _('Stone weight cannot exceed gross weight.'))

    @api.constrains('rfid_tag')
    def _check_rfid_unique(self):
        for lot in self.filtered('rfid_tag'):
            clash = self.search_count([
                ('id', '!=', lot.id),
                ('company_id', '=', lot.company_id.id),
                ('rfid_tag', '=', lot.rfid_tag),
            ])
            if clash:
                raise ValidationError(
                    _('RFID tag %s is already used by another piece.')
                    % lot.rfid_tag)

    def _vat_rate(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'mumtaz_jewellery.vat_rate')
        return float(param) if param else 0.0

    def get_price_breakdown(self, making_discount_pct=0.0):
        """Price from the approved database rate. Never from a model."""
        self.ensure_one()
        if not self.karat:
            raise ValidationError(_('Set the karat before pricing a piece.'))
        rate = self.env['jewellery.gold.rate'].get_current(
            self.company_id or self.env.company)
        out = pricing.price_piece(
            net_weight_g=self.net_weight_g,
            karat=int(self.karat),
            rate_24k_per_g=rate.rate_per_gram,
            wastage_pct=self.wastage_pct,
            making_type=self.making_type or 'percent',
            making_value=self.making_value,
            making_discount_pct=making_discount_pct,
            stones_value=self.stones_value,
            vat_rate=self._vat_rate(),
        )
        result = {key: float(value) for key, value in out.items()}
        result['rate_id'] = rate.id
        return result

    @api.depends('net_weight_g', 'karat', 'wastage_pct', 'making_type',
                 'making_value', 'stones_value')
    def _compute_jewellery_price(self):
        for lot in self:
            try:
                lot.jewellery_price = lot.get_price_breakdown()['total']
            except Exception:  # no approved rate yet, or piece incomplete
                lot.jewellery_price = 0.0
