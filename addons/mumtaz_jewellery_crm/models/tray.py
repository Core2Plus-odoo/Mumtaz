"""The Private Tray and the pipeline around it.

An opportunity (standard crm.lead) carries the client's moment through
Enquiry -> Tray shared -> Viewing booked -> Reserved -> Won. The tray is the
three-to-five-piece selection behind it: ranked by the deterministic policy
that stores its reasons, or chosen by hand for Private and Royal clients,
who are never scored. A tokenised link lets the client like, ask or request a
viewing from her phone; a request is not a reservation, staff reserve, and
the reservation is a draft quotation priced from the approved rate.
"""
import hashlib
import importlib.util
import os
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_spec = importlib.util.spec_from_file_location(
    'mumtaz_nbo', os.path.join(os.path.dirname(__file__), '..', '..', 'mumtaz_jewellery_vip',
                               'services', 'nbo.py'))
nbo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nbo)

POLICY_VERSION = 'nbo-1'
RESTRICTED = ('private', 'royal')
MAX_PIECES = 5
MIN_PIECES = 1


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class JewelleryTray(models.Model):
    _name = 'jewellery.tray'
    _description = 'Private tray'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(default=lambda s: _('New'), copy=False, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, index=True)
    user_id = fields.Many2one('res.users', string='Associate', default=lambda s: s.env.user)
    lead_id = fields.Many2one('crm.lead', string='Opportunity', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'), ('shared', 'Shared'), ('viewing', 'Viewing requested'),
        ('reserved', 'Reserved'), ('won', 'Won'), ('closed', 'Closed'),
    ], default='draft', required=True, tracking=True)
    intent = fields.Char(help='Occasion or purpose, in the client\'s words.')
    budget = fields.Float(help='Stated budget for this moment; falls back to the usual spend.')
    line_ids = fields.One2many('jewellery.tray.line', 'tray_id', string='Pieces')
    policy_version = fields.Char(default=POLICY_VERSION, readonly=True)
    stock_checked_at = fields.Datetime(readonly=True)
    # The link. Only the digest is stored; the token is shown once, on share.
    token_digest = fields.Char(index=True, copy=False, readonly=True)
    token_expires = fields.Datetime(copy=False, readonly=True)
    token_revoked = fields.Boolean(copy=False, readonly=True)
    link_opened_at = fields.Datetime(readonly=True)
    viewing_requested_at = fields.Datetime(readonly=True)
    viewing_preferred = fields.Char(readonly=True)
    viewing_note = fields.Char(readonly=True)
    reservation_order_id = fields.Many2one('sale.order', string='Reservation', readonly=True, copy=False)
    link_live = fields.Boolean(compute='_compute_link_live')

    @api.depends('token_digest', 'token_expires', 'token_revoked', 'state')
    def _compute_link_live(self):
        now = fields.Datetime.now()
        for tray in self:
            tray.link_live = bool(
                tray.token_digest and not tray.token_revoked
                and tray.token_expires and tray.token_expires > now
                and tray.state in ('shared', 'viewing'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('jewellery.tray') or _('New')
        return super().create(vals_list)

    # ---- eligibility: what may go on a tray ------------------------------
    @api.model
    def _lot_available(self, lot):
        """On the shelf, not on another live order, not out on approval."""
        if lot.product_qty <= 0:
            return False
        Line = self.env['sale.order.line'].sudo()
        if Line.search_count([('jewellery_lot_id', '=', lot.id), ('order_id.state', 'in', ('sale', 'done'))]):
            return False
        Memo = self.env['jewellery.approval.memo'].sudo()
        if Memo.search_count([('lot_ids', 'in', lot.id), ('state', '=', 'out')]):
            return False
        return True

    @api.model
    def _eligible_lots(self):
        lots = self.env['stock.quant'].sudo().search([
            ('location_id.usage', '=', 'internal'), ('quantity', '>', 0), ('lot_id', '!=', False),
            ('lot_id.product_id.product_tmpl_id.is_jewellery', '=', True),
        ]).mapped('lot_id')
        return lots.filtered(self._lot_available)

    # ---- building the tray -------------------------------------------------
    def _check_editable(self):
        for tray in self:
            if tray.state not in ('draft', 'shared'):
                raise UserError(_('Tray %s is %s and cannot be changed.') % (tray.name, tray.state))

    def action_build(self, limit=3):
        """Fill the tray from the ranking policy: eligible pieces only, with
        the reasons stored per line. Never for a Private or Royal client."""
        self.ensure_one()
        self._check_editable()
        if self.partner_id.jewellery_tier in RESTRICTED:
            raise UserError(_(
                'Private and Royal clients are not ranked. Choose the pieces for '
                '%s by hand.') % self.partner_id.display_name)
        limit = max(MIN_PIECES, min(MAX_PIECES, int(limit or 3)))
        pieces = []
        for lot in self._eligible_lots():
            try:
                b = lot.get_price_breakdown()
            except (UserError, ValidationError):
                continue
            sub = float(b['subtotal']) or 1.0
            pieces.append({
                'id': lot.id, 'name': lot.name, 'karat': lot.karat, 'price': float(b['total']),
                'margin_pct': (float(b['making_charge']) + float(b['wastage_value'])) / sub * 100,
                'occasions': [t.strip() for t in (lot.occasion_tags or '').split(',') if t.strip()],
            })
        partner = self.partner_id
        bought = self.env['sale.order.line'].sudo().search([
            ('order_id.partner_id', '=', partner.id), ('order_id.state', 'in', ('sale', 'done')),
            ('jewellery_lot_id', '!=', False)]).mapped('jewellery_lot_id').ids
        today = fields.Date.context_today(self)
        occasion = (self.intent or '').strip().lower() or None
        if not occasion:
            upcoming = None
            for occ in partner.occasion_ids:
                nxt = occ._next_date(today)
                if nxt >= today and (nxt - today).days <= 60 and (not upcoming or nxt < upcoming[0]):
                    upcoming = (nxt, occ.kind)
            occasion = upcoming[1] if upcoming else None
        prefs = {
            'karats': [k.strip() for k in (partner.preferred_karats or '').split(',') if k.strip()],
            'budget': self.budget or partner.typical_budget or None,
            'bought_ids': set(bought),
            'occasion': occasion,
        }
        ranked = nbo.rank_pieces(prefs, pieces, limit=limit)
        self.line_ids.unlink()
        self.write({
            'line_ids': [(0, 0, {
                'lot_id': r['id'], 'sequence': i + 1, 'price': r['price'],
                'reasons': '\n'.join(r['reasons']) or _('Eligible and in stock'),
                'score': r['score'],
            }) for i, r in enumerate(ranked)],
            'stock_checked_at': fields.Datetime.now(),
            'policy_version': POLICY_VERSION,
        })
        self._ensure_lead()
        return ranked

    def action_add_piece(self, lot, reasons=None):
        self.ensure_one()
        self._check_editable()
        if len(self.line_ids) >= MAX_PIECES:
            raise UserError(_('A tray holds at most %d pieces.') % MAX_PIECES)
        if lot in self.line_ids.mapped('lot_id'):
            return True
        if not self._lot_available(lot):
            raise UserError(_('Piece %s is not available to offer.') % lot.name)
        b = lot.get_price_breakdown()
        self.write({'line_ids': [(0, 0, {
            'lot_id': lot.id, 'sequence': len(self.line_ids) + 1, 'price': float(b['total']),
            'reasons': reasons or _('Chosen by %s') % self.env.user.name,
        })], 'stock_checked_at': fields.Datetime.now()})
        self._ensure_lead()
        return True

    def action_remove_piece(self, lot):
        self.ensure_one()
        self._check_editable()
        self.line_ids.filtered(lambda l: l.lot_id == lot).unlink()
        return True

    def action_refresh_eligibility(self):
        """Re-check every piece against stock and other sales; drop what is gone."""
        for tray in self:
            gone = tray.line_ids.filtered(lambda l: not self._lot_available(l.lot_id))
            if gone and tray.state in ('draft', 'shared', 'viewing'):
                tray.message_post(body=_('Dropped from the tray, no longer available: %s')
                                  % ', '.join(gone.mapped('lot_id.name')))
                gone.unlink()
            tray.stock_checked_at = fields.Datetime.now()
        return True

    # ---- the opportunity ---------------------------------------------------
    def _ensure_lead(self):
        for tray in self:
            if tray.lead_id:
                continue
            tray.lead_id = self.env['crm.lead'].create({
                'name': _('%(tray)s · %(client)s', tray=tray.name, client=tray.partner_id.name),
                'partner_id': tray.partner_id.id,
                'type': 'opportunity',
                'user_id': tray.user_id.id,
                'stage_id': self.env.ref('mumtaz_jewellery_crm.stage_enquiry').id,
                'expected_revenue': sum(tray.line_ids.mapped('price')),
            })
        return True

    def _set_stage(self, xmlid):
        stage = self.env.ref('mumtaz_jewellery_crm.' + xmlid)
        for tray in self:
            tray._ensure_lead()
            tray.lead_id.write({'stage_id': stage.id,
                                'expected_revenue': sum(tray.line_ids.mapped('price'))})

    # ---- the link ----------------------------------------------------------
    def action_share(self):
        """Open the link. Returns the plain token, once; only its digest is kept."""
        self.ensure_one()
        if self.state not in ('draft', 'shared'):
            raise UserError(_('Tray %s is %s.') % (self.name, self.state))
        if self.partner_id.jewellery_tier == 'royal':
            raise UserError(_(
                'A Royal client\'s tray does not leave the building. Show it in '
                'person; no link is made.'))
        if not MIN_PIECES <= len(self.line_ids) <= MAX_PIECES:
            raise UserError(_('A tray is shared with %d to %d pieces.') % (MIN_PIECES, MAX_PIECES))
        self.action_refresh_eligibility()
        if not self.line_ids:
            raise UserError(_('Nothing on the tray is available any more.'))
        days = self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.tray_link_days')
        days = int(days) if days else 7
        token = secrets.token_urlsafe(24)
        digest = _digest(token)
        for line in self.line_ids.sorted('sequence'):
            line.public_ref = hashlib.sha256(f'{digest}:{line.lot_id.id}'.encode()).hexdigest()[:10]
        self.write({
            'token_digest': digest,
            'token_expires': fields.Datetime.now() + timedelta(days=days),
            'token_revoked': False,
            'state': 'shared',
        })
        self._set_stage('stage_tray')
        self.message_post(body=_('Link shared by %s, valid %d days.') % (self.env.user.name, days))
        return token

    def action_revoke(self):
        for tray in self:
            tray.write({'token_revoked': True})
            tray.message_post(body=_('Link revoked by %s.') % self.env.user.name)
        return True

    @api.model
    def _find_by_token(self, token):
        """The tray behind a live link, or None. Sudo: the client has no user."""
        if not token or len(token) > 128:
            return None
        tray = self.sudo().search([('token_digest', '=', _digest(token))], limit=1)
        if not tray or not tray.link_live:
            return None
        return tray

    def _public_payload(self):
        """What the client's phone gets: pieces and prices, nothing about her,
        no internal ids. Availability is re-checked on every open."""
        self.ensure_one()
        self.sudo().action_refresh_eligibility()
        self.sudo().link_opened_at = fields.Datetime.now()
        company = self.company_id if 'company_id' in self._fields else self.env.company
        return {
            'tray': self.name,
            'expires': self.token_expires,
            'state': self.state,
            'currency': company.currency_id.name,
            'pieces': [{
                'ref': l.public_ref,
                'product': l.lot_id.product_id.name,
                'karat': l.lot_id.karat,
                'net_weight_g': l.lot_id.net_weight_g,
                'price': l.price,
                'why': l.reasons,
                'feedback': l.feedback,
                'question': l.question or None,
            } for l in self.line_ids.sorted('sequence')],
            'viewing_requested': bool(self.viewing_requested_at),
        }

    def _public_feedback(self, ref, kind, question=None):
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.public_ref == ref)[:1]
        if not line:
            raise UserError(_('No such piece on this tray.'))
        if kind not in ('like', 'dislike', 'question', 'clear'):
            raise UserError(_('Unknown feedback.'))
        vals = {}
        if kind in ('like', 'dislike'):
            vals['feedback'] = kind
        elif kind == 'clear':
            vals['feedback'] = 'none'
        if kind == 'question':
            vals['question'] = (question or '').strip()[:500]
        line.sudo().write(vals)
        if self.lead_id:
            body = _('Client feedback on %(piece)s: %(kind)s %(q)s',
                     piece=line.lot_id.name, kind=kind,
                     q=('— ' + vals['question']) if vals.get('question') else '')
            self.lead_id.sudo().message_post(body=body)
        return True

    def _public_request_viewing(self, preferred=None, note=None):
        """A request is not a reservation: it opens an activity for staff."""
        self.ensure_one()
        tray = self.sudo()
        tray.write({
            'state': 'viewing',
            'viewing_requested_at': fields.Datetime.now(),
            'viewing_preferred': (preferred or '').strip()[:120],
            'viewing_note': (note or '').strip()[:500],
        })
        tray._set_stage('stage_viewing')
        tray.lead_id.activity_schedule(
            'mail.mail_activity_data_todo',
            date_deadline=fields.Date.context_today(self) + timedelta(days=1),
            summary=_('Viewing requested from the tray link'),
            note=_('Preferred: %(p)s. Note: %(n)s. Confirm availability and book the viewing.',
                   p=tray.viewing_preferred or '—', n=tray.viewing_note or '—'),
            user_id=tray.user_id.id or self.env.uid)
        return True

    # ---- the reservation: a draft quotation ----------------------------------
    def action_reserve(self, lot):
        self.ensure_one()
        if self.state not in ('shared', 'viewing', 'draft'):
            raise UserError(_('Tray %s is %s.') % (self.name, self.state))
        if lot not in self.line_ids.mapped('lot_id'):
            raise UserError(_('Piece %s is not on this tray.') % lot.name)
        if not self._lot_available(lot):
            raise UserError(_('Piece %s is no longer available.') % lot.name)
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.env.user.id,
            'origin': self.name,
            'order_line': [(0, 0, {'product_id': lot.product_id.id, 'product_uom_qty': 1,
                                   'jewellery_lot_id': lot.id})],
        })
        order.order_line.action_price_from_rate()
        self.write({'reservation_order_id': order.id, 'state': 'reserved', 'token_revoked': True})
        self._set_stage('stage_reserved')
        self.message_post(body=_('Reserved %(piece)s on %(order)s by %(user)s.',
                                 piece=lot.name, order=order.name, user=self.env.user.name))
        return order

    def action_close(self):
        self.write({'state': 'closed', 'token_revoked': True})
        return True


class JewelleryTrayLine(models.Model):
    _name = 'jewellery.tray.line'
    _description = 'Private tray piece'
    _order = 'sequence, id'

    tray_id = fields.Many2one('jewellery.tray', required=True, ondelete='cascade', index=True)
    lot_id = fields.Many2one('stock.lot', string='Piece', required=True)
    sequence = fields.Integer(default=1)
    score = fields.Float(readonly=True)
    reasons = fields.Text(readonly=True)
    price = fields.Float(digits=(16, 2), readonly=True,
                         help='Engine price incl. VAT when the piece was put on the tray.')
    feedback = fields.Selection([('none', '—'), ('like', 'Liked'), ('dislike', 'Not for her')],
                                default='none')
    question = fields.Text()
    public_ref = fields.Char(readonly=True, copy=False)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    tray_ids = fields.One2many('jewellery.tray', 'reservation_order_id', string='Trays')

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            for tray in order.tray_ids.filtered(lambda t: t.state == 'reserved'):
                tray.write({'state': 'won'})
                if tray.lead_id:
                    tray.lead_id.action_set_won()
        return res


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    jewellery_tray_ids = fields.One2many('jewellery.tray', 'lead_id', string='Private trays')
