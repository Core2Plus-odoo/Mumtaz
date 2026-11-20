"""A client's sign-in: a phone, a six-digit code for ten minutes that a
person gives her (the server sends nothing), then a token for thirty days.
What the token may read is her own: the pieces she bought, the selections
prepared for her, her requests, her consent."""
import hashlib
import re
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

CODE_MINUTES = 10
TOKEN_DAYS = 30
MAX_ATTEMPTS = 5
CODES_PER_HOUR = 3


def clean_phone(phone):
    return re.sub(r'[^0-9+]', '', phone or '')[:20]


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class ClientSession(models.Model):
    _name = 'jewellery.client.session'
    _description = 'Client app sign-in'
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', string='Client', required=True, ondelete='cascade', index=True)
    phone = fields.Char(required=True, index=True)
    lang = fields.Char(default='en')
    code = fields.Char(help='The one-time code while it is valid; cleared when used or expired.')
    code_expires = fields.Datetime()
    attempts = fields.Integer(default=0)
    token_digest = fields.Char(index=True, copy=False)
    token_expires = fields.Datetime()
    verified_at = fields.Datetime()
    last_seen = fields.Datetime()
    revoked = fields.Boolean(default=False)
    state = fields.Selection([('code', 'Code issued'), ('open', 'Signed in'), ('closed', 'Closed')], compute='_compute_state')

    @api.depends('code', 'code_expires', 'token_digest', 'token_expires', 'revoked')
    def _compute_state(self):
        now = fields.Datetime.now()
        for s in self:
            if s.revoked:
                s.state = 'closed'
            elif s.token_digest and s.token_expires and s.token_expires > now:
                s.state = 'open'
            elif s.code and s.code_expires and s.code_expires > now:
                s.state = 'code'
            else:
                s.state = 'closed'

    # -- the code --------------------------------------------------------
    @api.model
    def request_code(self, phone, lang='en'):
        """Create a code for the client with this phone. The answer is the
        same for a phone we do not know, so the door does not say who is a
        client. The code is given to her by a person; it is not sent."""
        phone = clean_phone(phone)
        if len(phone) < 7:
            raise UserError(_('Give the phone number the shop has for you.'))
        now = fields.Datetime.now()
        partner = self._partner_by_phone(phone)
        echo = self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.client_code_echo') == '1'
        out = {'ok': True, 'message': _('If this phone is known to us, a code is on its way through your advisor.'),
               'minutes': CODE_MINUTES}
        if not partner:
            return out
        recent = self.sudo().search_count([('phone', '=', phone), ('create_date', '>=', now - timedelta(hours=1))])
        if recent >= CODES_PER_HOUR:
            return out        # the same answer: no new code, no hint
        code = '%06d' % secrets.randbelow(1000000)
        self.sudo().create({'partner_id': partner.id, 'phone': phone, 'lang': (lang or 'en')[:5],
                            'code': code, 'code_expires': now + timedelta(minutes=CODE_MINUTES)})
        if echo:
            out['code'] = code          # demo only; the parameter documents it
        return out

    @api.model
    def _partner_by_phone(self, phone):
        """The client whose phone, once cleaned of spaces and dashes, is
        this one. Phones are stored as typed, so compare cleaned."""
        # Phones are stored as typed ("+971 50 123 4567"), so only the last
        # four digits are a safe contiguous match; the cleaned compare decides.
        tail = phone[-4:]
        for p in self.env['res.partner'].sudo().search([('phone', 'ilike', tail), ('is_company', '=', False)], limit=500):
            if clean_phone(p.phone) == phone:
                return p
        return self.env['res.partner'].sudo().browse()

    @api.model
    def verify(self, phone, code):
        """The code she was given, against the newest valid one for her
        phone. Five misses close it. Success gives a token; the code is gone."""
        phone = clean_phone(phone)
        code = (code or '').strip()
        now = fields.Datetime.now()
        sess = self.sudo().search([('phone', '=', phone), ('code', '!=', False), ('code_expires', '>', now),
                                   ('revoked', '=', False)], order='id desc', limit=1)
        if not sess or not code:
            return {'ok': False, 'error': _('That code is not valid any more. Ask your advisor for a new one.')}
        if sess.code != code:
            # A miss is a result, not an error: an error would roll the
            # request back and the count of misses with it.
            sess.attempts += 1
            if sess.attempts >= MAX_ATTEMPTS:
                sess.write({'code': False, 'code_expires': False})
            return {'ok': False, 'error': _('That code is not right.')}
        token = secrets.token_urlsafe(32)
        sess.write({'code': False, 'code_expires': False, 'token_digest': _digest(token),
                    'token_expires': now + timedelta(days=TOKEN_DAYS), 'verified_at': now, 'last_seen': now})
        return {'ok': True, 'token': token, 'session': sess}

    @api.model
    def by_token(self, token):
        if not token:
            return self.browse()
        now = fields.Datetime.now()
        sess = self.sudo().search([('token_digest', '=', _digest(token)), ('revoked', '=', False),
                                   ('token_expires', '>', now)], limit=1)
        if sess:
            sess.last_seen = now
        return sess

    def action_revoke(self):
        self.sudo().write({'revoked': True, 'code': False, 'token_digest': False})
        return True

    @api.model
    def _cron_expire(self):
        now = fields.Datetime.now()
        self.sudo().search([('code', '!=', False), ('code_expires', '<', now)]).write({'code': False})
        self.sudo().search([('token_digest', '!=', False), ('token_expires', '<', now)]).write({'token_digest': False})

    @api.model
    def pending_codes(self, partner):
        """What staff may read to her: the live code, for her record only."""
        now = fields.Datetime.now()
        return [{'code': s.code, 'expires': s.code_expires, 'requested_at': s.create_date}
                for s in self.sudo().search([('partner_id', '=', partner.id), ('code', '!=', False), ('code_expires', '>', now)])]

    # -- what she may read -----------------------------------------------
    def owned_pieces(self):
        """The pieces she bought: lines of confirmed orders with a serial."""
        self.ensure_one()
        partner = self.partner_id
        lines = self.env['sale.order.line'].sudo().search([
            ('order_id.partner_id', 'child_of', partner.commercial_partner_id.id), ('order_id.state', 'in', ('sale', 'done')),
            ('jewellery_lot_id', '!=', False)], order='id desc')
        rate = None
        try:
            rate = self.env['jewellery.gold.rate'].sudo().get_current(self.env.company).rate_per_gram
        except UserError:
            rate = None
        out = []
        for l in lines:
            lot = l.jewellery_lot_id
            fine = (lot.net_weight_g or 0.0) * float(lot.karat or 0) / 24.0
            inv = l.order_id.invoice_ids.filtered(lambda m: m.state == 'posted')[:1]
            out.append({
                'serial': lot.name, 'design': lot.product_id.name, 'category': lot.product_id.jewellery_category or None,
                'karat': lot.karat, 'net_weight_g': lot.net_weight_g, 'fine_g': round(fine, 3),
                'bought_on': l.order_id.date_order.date() if l.order_id.date_order else None, 'order': l.order_id.name,
                'invoice': inv.name if inv else None, 'paid': l.price_total,
                'metal_value_today': round(fine * rate, 2) if rate else None,
                'image_url': '/jawhar/client/pieces/%s/image' % lot.name if lot.product_id.image_1024 else None,
            })
        return out

    def trays(self):
        self.ensure_one()
        Tray = self.env['jewellery.tray'].sudo()
        out = []
        for t in Tray.search([('partner_id', '=', self.partner_id.id), ('state', 'in', ('shared', 'viewing', 'reserved'))], order='id desc', limit=10):
            out.append({'id': t.id, 'name': t.name, 'state': t.state, 'pieces': len(t.line_ids), 'shared_at': t.token_expires and t.create_date,
                        'link_live': t.link_live})
        return out

    def requests(self):
        self.ensure_one()
        Req = self.env['jewellery.kiosk.request'].sudo()
        recs = Req.search(['|', ('partner_id', '=', self.partner_id.id), ('phone', '=', self.phone)], order='id desc', limit=10)
        return [{'id': r.id, 'name': r.name, 'kind': r.kind, 'state': r.state, 'serial': r.serial, 'design': r.lot_id.product_id.name,
                 'at': r.create_date, 'price_quoted': r.price_quoted} for r in recs]

    def me(self):
        self.ensure_one()
        p = self.partner_id
        return {'first_name': (p.name or '').split(' ')[0], 'name': p.name, 'lang': p.lang or None,
                'consent': {'status': p.marketing_consent, 'may_message': p.may_message},
                'advisor': p.relationship_manager_id.name or None, 'signed_in_at': self.verified_at}
