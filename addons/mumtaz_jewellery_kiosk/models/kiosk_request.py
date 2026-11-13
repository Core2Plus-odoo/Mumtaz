"""A client's request from the kiosk: a viewing, or next-day delivery.

Written by the public user with nothing but what the client typed or said;
read and decided by staff. Confirmation is where the shop's own rules take
over: the client record, the opportunity, a draft quotation priced from the
approved rate. Nothing here touches stock.
"""
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

KINDS = [('viewing', 'Viewing / set aside'), ('delivery', 'Next-day delivery')]
STATES = [('requested', 'Requested'), ('confirmed', 'Confirmed'), ('declined', 'Declined'), ('done', 'Done')]
SLOTS = [('morning', 'Morning'), ('afternoon', 'Afternoon')]


def _clean_phone(phone):
    return re.sub(r'[^0-9+]', '', phone or '')[:20]


class KioskRequest(models.Model):
    _name = 'jewellery.kiosk.request'
    _description = 'Kiosk request (Virtual Sales Officer)'
    _order = 'id desc'
    _inherit = ['mail.thread']

    name = fields.Char(default=lambda s: _('New'), copy=False, readonly=True)
    kind = fields.Selection(KINDS, required=True, index=True)
    state = fields.Selection(STATES, default='requested', required=True, index=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    lot_id = fields.Many2one('stock.lot', string='Piece', required=True, ondelete='restrict')
    serial = fields.Char(related='lot_id.name', store=True)
    price_quoted = fields.Float(digits=(16, 2), readonly=True,
                                help='The engine price shown to the client at request time, for the record.')
    client_name = fields.Char(required=True)
    phone = fields.Char(required=True, index=True)
    preferred_time = fields.Char()
    address = fields.Text()
    slot = fields.Selection(SLOTS)
    delivery_date = fields.Date()
    note = fields.Text()
    fit_notes = fields.Char(
        readonly=True,
        help='What the try-on estimated on the client (height, wrist, ring size, where a chain sits). '
             'Estimates from the kiosk camera, for the fitter to confirm in person; nothing else from the camera is kept.')
    lang = fields.Char(default='en')
    channel = fields.Selection([('store', 'In-store kiosk'), ('web', 'Website')], default='store')
    partner_id = fields.Many2one('res.partner', string='Client', readonly=True)
    lead_id = fields.Many2one('crm.lead', readonly=True)
    order_id = fields.Many2one('sale.order', string='Draft quotation', readonly=True)
    decided_by_id = fields.Many2one('res.users', readonly=True)
    decided_at = fields.Datetime(readonly=True)
    decline_reason = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('jewellery.kiosk.request') or _('New')
        return super().create(vals_list)

    # -- the public side ---------------------------------------------------
    @api.model
    def _cap(self):
        param = self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.kiosk_daily_cap')
        try:
            return max(1, int(param))
        except (TypeError, ValueError):
            return 3

    @api.model
    def create_public(self, kind, serial, client_name, phone, preferred_time=None, address=None,
                      slot=None, note=None, lang='en', channel='store', fit=None):
        """What the kiosk may do: one request, validated, capped, logged.
        Runs under sudo for the public user; returns a payload with no
        internal ids."""
        if kind not in dict(KINDS):
            raise UserError(_('Unknown request.'))
        client_name = (client_name or '').strip()[:80]
        phone = _clean_phone(phone)
        if len(client_name) < 2 or len(phone) < 7:
            raise UserError(_('A name and a phone number are needed so a colleague can call you back.'))
        lot = self.env['stock.lot'].sudo().search([('name', '=', (serial or '').strip()), ('product_id.is_jewellery', '=', True)], limit=1)
        if not lot or not self.env['jewellery.tray'].sudo()._lot_public(lot):
            raise UserError(_('That piece is not on the shelf any more. Ask about another.'))
        if kind == 'delivery' and (not address or len(address.strip()) < 8 or slot not in dict(SLOTS)):
            raise UserError(_('Delivery needs an address and a morning or afternoon slot.'))
        since = fields.Datetime.now() - timedelta(days=1)
        if self.sudo().search_count([('phone', '=', phone), ('create_date', '>=', since)]) >= self._cap():
            raise UserError(_('That number has already placed several requests today. A colleague will call you.'))
        try:
            price = float(lot.get_price_breakdown()['total'])
        except Exception:  # noqa: BLE001 -- the price is for the record only
            price = 0.0
        rec = self.sudo().create({
            'kind': kind, 'lot_id': lot.id, 'price_quoted': price, 'client_name': client_name, 'phone': phone,
            'preferred_time': (preferred_time or '')[:120] or False, 'address': (address or '')[:400] or False,
            'slot': slot if kind == 'delivery' else False,
            'delivery_date': fields.Date.context_today(self) + timedelta(days=1) if kind == 'delivery' else False,
            'note': (note or '')[:500] or False, 'fit_notes': self._fit_notes(fit) or False,
            'lang': 'ar' if (lang or '').startswith('ar') else 'en',
            'channel': channel if channel in ('store', 'web') else 'store',
        })
        return rec._public_dict()

    # What the try-on may hand over, and the bounds a human body stays within.
    FIT_KEYS = {
        'height_cm': (120, 210, 0), 'wrist_girth_mm': (100, 250, 0), 'neck_girth_mm': (250, 500, 0),
        'ring_eu': (40, 75, 0), 'ring_us': (3, 13, 1),
    }
    FIT_WORDS = {'bangle': {'2-2', '2-4', '2-6', '2-8', '2-10', '2-12', '2-14'},
                 'chain_sits': {'choker', 'collarbone', 'below_collarbone', 'bust', 'long'},
                 'verdict': {'tight', 'fits', 'loose'}}

    @api.model
    def _fit_notes(self, fit):
        """One line for the fitter from the try-on's estimates: whitelisted
        keys, numbers within human bounds, words from a fixed list. Anything
        else is dropped; nothing is ever raised over it."""
        if not isinstance(fit, dict):
            return ''
        parts = []
        for key, (lo, hi, digits) in self.FIT_KEYS.items():
            try:
                value = float(fit.get(key))
            except (TypeError, ValueError):
                continue
            if lo <= value <= hi:
                parts.append('%s %s' % (key.replace('_', ' '), round(value, digits) if digits else int(round(value))))
        for key, allowed in self.FIT_WORDS.items():
            value = fit.get(key)
            if isinstance(value, str) and value in allowed:
                parts.append('%s %s' % (key.replace('_', ' '), value))
        if not parts:
            return ''
        return (_('Try-on estimates: %s') % '; '.join(parts))[:300]

    def _public_dict(self):
        self.ensure_one()
        return {
            'reference': self.name, 'kind': self.kind, 'state': self.state, 'serial': self.serial,
            'delivery_date': self.delivery_date, 'slot': self.slot,
            'message': (_('Thank you, %s. A colleague will call %s to confirm. Nothing is reserved or charged until then.')
                        % (self.client_name.split(' ')[0], self.phone)),
        }

    # -- the staff side ----------------------------------------------------
    def _find_or_create_partner(self):
        self.ensure_one()
        Partner = self.env['res.partner']
        partner = Partner.search([('phone', '=', self.phone), ('is_company', '=', False)], limit=1)
        if not partner:
            installed = self.env['res.lang'].search([('code', '=', 'ar_001')], limit=1)
            partner = Partner.create({'name': self.client_name, 'phone': self.phone, 'is_company': False,
                                      'lang': 'ar_001' if self.lang == 'ar' and installed else False,
                                      'comment': _('Created from a kiosk request %s.') % self.name})
        return partner

    def action_confirm(self):
        """A person confirms: the client exists, the opportunity is open, a
        draft quotation is priced from the approved rate. Stock is untouched;
        the sale confirms and pays as at the counter."""
        for rec in self:
            if rec.state != 'requested':
                raise UserError(_('%s is not waiting.') % rec.name)
            if not self.env['jewellery.tray']._lot_available(rec.lot_id):
                raise UserError(_('Piece %s is no longer available; decline and tell the client.') % rec.serial)
            partner = rec._find_or_create_partner()
            if partner.jewellery_restricted:
                partner.check_access('read')
            lead = self.env['crm.lead'].create({
                'name': _('%(kind)s · %(serial)s · %(client)s', kind=dict(KINDS)[rec.kind], serial=rec.serial, client=partner.name),
                'partner_id': partner.id, 'type': 'opportunity', 'user_id': self.env.user.id,
                'stage_id': self.env.ref('mumtaz_jewellery_crm.stage_enquiry').id,
                'expected_revenue': rec.price_quoted,
                'description': _('Kiosk request %(ref)s. Address: %(addr)s. Slot: %(slot)s on %(date)s. Note: %(note)s',
                                 ref=rec.name, addr=rec.address or '-', slot=rec.slot or '-', date=rec.delivery_date or '-', note=rec.note or '-'),
            })
            order = self.env['sale.order'].create({
                'partner_id': partner.id, 'user_id': self.env.user.id, 'origin': rec.name, 'opportunity_id': lead.id,
                'order_line': [(0, 0, {'product_id': rec.lot_id.product_id.id, 'product_uom_qty': 1, 'jewellery_lot_id': rec.lot_id.id})],
            })
            order.order_line.action_price_from_rate()
            rec.write({'state': 'confirmed', 'partner_id': partner.id, 'lead_id': lead.id, 'order_id': order.id,
                       'decided_by_id': self.env.user.id, 'decided_at': fields.Datetime.now()})
            if rec.kind == 'delivery':
                lead.activity_schedule('mail.mail_activity_data_todo', date_deadline=rec.delivery_date,
                                       summary=_('Next-day delivery %s: confirm payment, then dispatch') % rec.slot,
                                       user_id=self.env.user.id)
        return True

    def action_decline(self, reason=None):
        for rec in self:
            if rec.state != 'requested':
                raise UserError(_('%s is not waiting.') % rec.name)
            rec.write({'state': 'declined', 'decline_reason': (reason or '')[:200] or False,
                       'decided_by_id': self.env.user.id, 'decided_at': fields.Datetime.now()})
        return True

    def action_done(self):
        self.filtered(lambda r: r.state == 'confirmed').write({'state': 'done'})
        return True
