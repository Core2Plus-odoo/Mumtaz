"""Jawhar API, version 1.

One door for the Jawhar interface. Design rules, each of which a test holds:

* Every endpoint runs as the signed-in Odoo user. Access rights and record
  rules do the filtering; this layer adds nothing and removes nothing, so what
  the API shows is exactly what that person could see in the web client.
* Figures are read from Odoo. The price breakdown comes from
  ``stock.lot.get_price_breakdown()``, which calls the pricing engine against
  the approved rate. Nothing here multiplies, rounds or guesses.
* Every call leaves an audit row, including the ones that fail. The handler
  runs inside a savepoint; an error rolls back the handler's work only, and
  the audit row written afterwards is committed with the request.
* Unauthenticated calls get a JSON 401, never a redirect to /web/login: the
  caller is a program, not a browser looking for a form.

Transport: plain HTTP + JSON (``type='http'``), not JSON-RPC, so the front end
and any other client speak ordinary REST. CSRF: the routes are ``csrf=False``
because the session cookie is SameSite and every state-changing call must be
sent with ``Content-Type: application/json``, which a cross-site form cannot
produce without a CORS preflight that Odoo does not answer.
"""
import functools
import logging
import time

from odoo import SUPERUSER_ID, api, fields
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

PREFIX = '/jawhar/v1'
API_VERSION = '1.0'
MAX_LIMIT = 200

# Groups the interface cares about, as short role names.
ROLE_GROUPS = {
    'jewellery_user': 'mumtaz_jewellery.group_jewellery_user',
    'jewellery_manager': 'mumtaz_jewellery.group_jewellery_manager',
    'vip_manager': 'mumtaz_jewellery_vip.group_vip_manager',
    'sales': 'sales_team.group_sale_salesman',
    'accounting': 'account.group_account_invoice',
    'admin': 'base.group_system',
}

QUOTE_STATES = ('draft', 'sent')
ORDER_STATES = ('sale',)

# A client is a partner placed in a tier above standard, or one who has bought.
# `!= 'standard'` would also match partners with no tier at all (every user's
# own partner, the company), which is why the tiers are listed.
CLIENT_DOMAIN = ['|', ('jewellery_tier', 'in', ('preferred', 'private', 'royal')),
                 ('customer_rank', '>', 0)]


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status, code, message):
        # All three go to the base class so the exception survives pickling
        # and copy.copy() (flake8-bugbear B042).
        super().__init__(status, code, message)
        self.status = status
        self.code = code
        self.message = message


def _json(data, status=200):
    return request.make_json_response({'ok': True, 'data': data}, status=status)


def _fail(status, code, message):
    return request.make_json_response(
        {'ok': False, 'error': {'code': code, 'message': message}}, status=status)


def _body():
    """The JSON body of a POST, or {} when there is none."""
    raw = request.httprequest.get_data(as_text=True)
    if not raw:
        return {}
    try:
        data = request.get_json_data()
    except ValueError:
        raise ApiError(400, 'bad_json', 'The request body is not valid JSON.')
    if not isinstance(data, dict):
        raise ApiError(400, 'bad_json', 'The request body must be a JSON object.')
    return data


def _int(value, default, lo=0, hi=MAX_LIMIT):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def _audit(status, started, error=None, login=None):
    """Written after the handler, on the request cursor, outside its savepoint."""
    try:
        env = api.Environment(request.env.cr, SUPERUSER_ID, {})
        user = request.env.user
        env['jewellery.api.audit'].create({
            'user_id': user.id if user and not user._is_public() else False,
            'login': login,
            'method': request.httprequest.method,
            'path': request.httprequest.path,
            'status': status,
            'duration_ms': int((time.monotonic() - started) * 1000),
            'remote_addr': request.httprequest.remote_addr,
            'error': error,
        })
    except Exception:  # noqa: BLE001 -- the audit must never break the call
        _logger.exception('Jawhar API: could not write the audit row')


def endpoint(auth=True):
    """Wrap a handler: auth check, savepoint, error mapping, audit."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kw):
            started = time.monotonic()
            status, error, login = 200, None, None
            try:
                if auth and request.env.user._is_public():
                    raise ApiError(401, 'unauthenticated', 'Sign in first.')
                with request.env.cr.savepoint():
                    result = fn(self, *args, **kw)
                if isinstance(result, tuple):
                    result, status = result
                return _json(result, status)
            except ApiError as e:
                status, error = e.status, e.code
                login = getattr(e, 'login', None)
                return _fail(e.status, e.code, e.message)
            except AccessDenied:
                status, error = 401, 'access_denied'
                return _fail(401, 'access_denied', 'Wrong login or password.')
            except AccessError as e:
                status, error = 403, 'forbidden'
                return _fail(403, 'forbidden', str(e.args[0]) if e.args else 'Not allowed.')
            except MissingError:
                status, error = 404, 'not_found'
                return _fail(404, 'not_found', 'No such record.')
            except (UserError, ValidationError) as e:
                status, error = 400, 'invalid'
                return _fail(400, 'invalid', str(e.args[0]) if e.args else 'Invalid request.')
            except Exception as e:  # noqa: BLE001
                status, error = 500, type(e).__name__
                _logger.exception('Jawhar API: unhandled error')
                return _fail(500, 'server_error', 'Something went wrong on the server.')
            finally:
                _audit(status, started, error=error, login=login)
        return wrapper
    return deco


def _get(model, rec_id):
    """A record by id, or 404.

    A record the person may not read is also a 404, not a 403: a 403 would
    confirm that the id exists, and for a Private or Royal client whose
    very presence is restricted, that confirmation is the leak.
    """
    rec = request.env[model].browse(int(rec_id)).exists()
    if not rec:
        raise ApiError(404, 'not_found', 'No such record.')
    try:
        rec.check_access('read')
    except AccessError:
        raise ApiError(404, 'not_found', 'No such record.')
    return rec


def _m2o(rec):
    return {'id': rec.id, 'name': rec.display_name} if rec else None


def _money(company):
    cur = company.currency_id
    return {'code': cur.name, 'symbol': cur.symbol, 'decimals': cur.decimal_places}


# --------------------------------------------------------------------------
# serialisers -- plain dicts, nothing computed here
# --------------------------------------------------------------------------
def _user_dict(user):
    roles = [name for name, xmlid in ROLE_GROUPS.items() if user.has_group(xmlid)]
    company = user.company_id
    return {
        'id': user.id,
        'name': user.name,
        'login': user.login,
        'email': user.email or None,
        'lang': user.lang,
        'tz': user.tz or None,
        'roles': roles,
        'company': {'id': company.id, 'name': company.name, 'currency': _money(company)},
    }


def _rate_dict(rate):
    return {
        'id': rate.id,
        'rate_per_gram': rate.rate_per_gram,
        'currency': rate.currency_id.name,
        'effective_at': rate.effective_at,
        'source': rate.source,
        'state': rate.state,
        'created_by': _m2o(rate.create_uid),
        'approved_by': _m2o(rate.approved_by_id),
        'approved_at': rate.approved_at,
    }


def _piece_location(lot):
    quant = lot.quant_ids.filtered(
        lambda q: q.quantity > 0 and q.location_id.usage == 'internal')[:1]
    return _m2o(quant.location_id) if quant else None


def _piece_dict(lot):
    return {
        'id': lot.id,
        'serial': lot.name,
        'product': _m2o(lot.product_id),
        'karat': lot.karat,
        'gross_weight_g': lot.gross_weight_g,
        'stone_weight_g': lot.stone_weight_g,
        'net_weight_g': lot.net_weight_g,
        'wastage_pct': lot.wastage_pct,
        'making_type': lot.making_type,
        'making_value': lot.making_value,
        'stones_value': lot.stones_value,
        'rfid_tag': lot.rfid_tag or None,
        'certificate_ref': lot.certificate_ref or None,
        'price_incl_vat': lot.jewellery_price,
        'on_hand': lot.product_qty,
        'location': _piece_location(lot),
    }


def _client_dict(partner, detail=False):
    data = {
        'id': partner.id,
        'name': partner.name,
        'tier': partner.jewellery_tier,
        'restricted': partner.jewellery_restricted,
        'ai_autonomy_cap': partner.ai_autonomy_cap,
        'relationship_manager': _m2o(partner.relationship_manager_id),
        'deputy': _m2o(partner.deputy_id),
        'phone': partner.phone or None,
        'email': partner.email or None,
        'city': partner.city or None,
        'no_marketing': partner.no_marketing,
        'lifetime_value': partner.lifetime_value,
    }
    if detail:
        data.update({
            'preferred_karats': partner.preferred_karats or None,
            'typical_budget': partner.typical_budget,
            'taste_notes': partner.taste_notes or None,
            'discreet_billing': partner.discreet_billing,
            'occasions': [{
                'id': o.id, 'kind': o.kind, 'date': o.date,
                'recurring': o.recurring, 'note': o.note or None,
            } for o in partner.occasion_ids],
            'memos': [_memo_dict(m) for m in partner.memo_ids],
        })
    return data


def _memo_dict(memo):
    return {
        'id': memo.id,
        'name': memo.name,
        'client': _m2o(memo.partner_id),
        'pieces': [{'id': l.id, 'serial': l.name, 'product': _m2o(l.product_id)}
                   for l in memo.lot_ids],
        'date_out': memo.date_out,
        'return_by': memo.return_by,
        'state': memo.state,
        'insured_value': memo.insured_value,
    }


def _card_dict(card):
    return {
        'id': card.id,
        'kind': card.kind,
        'title': card.title,
        'detail': card.detail or None,
        'recommendation': card.recommendation or None,
        'impact': card.impact or None,
        'priority': card.priority,
        'restricted': card.restricted,
        'state': card.state,
        'link': {'model': card.res_model, 'id': card.res_id} if card.res_model else None,
    }


def _order_line_dict(line):
    return {
        'id': line.id,
        'description': line.name,
        'product': _m2o(line.product_id),
        'piece': {'id': line.jewellery_lot_id.id, 'serial': line.jewellery_lot_id.name}
                 if line.jewellery_lot_id else None,
        'qty': line.product_uom_qty,
        'price_unit': line.price_unit,
        'subtotal': line.price_subtotal,
        'tax': line.price_tax,
        'total': line.price_total,
        'making_discount_pct': line.jewellery_making_discount_pct,
        'priced': line.jewellery_is_priced,
        'snapshot': {
            'rate_id': line.jewellery_rate_id.id,
            'rate_per_gram': line.jewellery_rate_per_gram,
            'fine_weight_g': line.jewellery_fine_weight_g,
            'metal_value': line.jewellery_metal_value,
            'wastage_value': line.jewellery_wastage_value,
            'making_charge': line.jewellery_making_charge,
            'stones_value': line.jewellery_stones_value,
            'priced_on': line.jewellery_priced_on,
        } if line.jewellery_is_priced else None,
    }


def _order_dict(order, detail=False):
    data = {
        'id': order.id,
        'name': order.name,
        'client': _m2o(order.partner_id),
        'salesperson': _m2o(order.user_id),
        'date': order.date_order,
        'state': order.state,
        'kind': 'quote' if order.state in QUOTE_STATES else 'order',
        'amount_untaxed': order.amount_untaxed,
        'amount_tax': order.amount_tax,
        'amount_total': order.amount_total,
        'currency': order.currency_id.name,
        'line_count': len(order.order_line),
        'invoice_status': order.invoice_status,
    }
    if detail:
        data['lines'] = [_order_line_dict(l) for l in order.order_line]
        data['invoices'] = [_m2o(m) for m in order.invoice_ids]
    return data


def _invoice_dict(move, detail=False):
    data = {
        'id': move.id,
        'name': move.name,
        'client': _m2o(move.partner_id),
        'date': move.invoice_date,
        'due_date': move.invoice_date_due,
        'state': move.state,
        'payment_state': move.payment_state,
        'amount_untaxed': move.amount_untaxed,
        'amount_tax': move.amount_tax,
        'amount_total': move.amount_total,
        'amount_residual': move.amount_residual,
        'currency': move.currency_id.name,
        'origin': move.invoice_origin or None,
    }
    if detail:
        data['lines'] = [{
            'id': l.id,
            'description': l.name,
            'product': _m2o(l.product_id),
            'piece': {'id': l.jewellery_lot_id.id, 'serial': l.jewellery_lot_id.name}
                     if l.jewellery_lot_id else None,
            'qty': l.quantity,
            'price_unit': l.price_unit,
            'subtotal': l.price_subtotal,
            'total': l.price_total,
            'snapshot': {
                'rate_per_gram': l.jewellery_rate_per_gram,
                'fine_weight_g': l.jewellery_fine_weight_g,
                'metal_value': l.jewellery_metal_value,
                'wastage_value': l.jewellery_wastage_value,
                'making_charge': l.jewellery_making_charge,
                'stones_value': l.jewellery_stones_value,
                'priced_on': l.jewellery_priced_on,
            } if l.jewellery_is_priced else None,
        } for l in move.invoice_line_ids]
    return data


def _old_gold_dict(x):
    return {
        'id': x.id,
        'name': x.name,
        'client': _m2o(x.partner_id),
        'date': x.date,
        'gross_weight_g': x.gross_weight_g,
        'karat': x.karat,
        'fine_weight_g': x.fine_weight_g,
        'applied_rate_per_g': x.applied_rate_per_g,
        'value': x.value,
        'state': x.state,
    }


# --------------------------------------------------------------------------
# the routes
# --------------------------------------------------------------------------
def _r(path, **kw):
    kw.setdefault('type', 'http')
    kw.setdefault('auth', 'public')
    kw.setdefault('csrf', False)
    kw.setdefault('methods', ['GET'])
    return route(PREFIX + path, **kw)


class JawharApi(Controller):

    # ---- meta -----------------------------------------------------------
    @_r('/health')
    @endpoint(auth=False)
    def health(self):
        return {'service': 'jawhar-api', 'version': API_VERSION,
                'odoo': request.env['ir.module.module'].sudo().search(
                    [('name', '=', 'mumtaz_jewellery_api')], limit=1).installed_version or None}

    # ---- auth -----------------------------------------------------------
    @_r('/auth/login', methods=['POST'])
    @endpoint(auth=False)
    def login(self):
        body = _body()
        login = (body.get('login') or '').strip()
        password = body.get('password') or ''
        if not login or not password:
            raise ApiError(400, 'missing_credentials', 'Send both login and password.')
        try:
            request.session.authenticate(
                request.env, {'login': login, 'password': password, 'type': 'password'})
        except AccessDenied:
            err = ApiError(401, 'access_denied', 'Wrong login or password.')
            err.login = login
            raise err
        return _user_dict(request.env.user)

    @_r('/auth/logout', methods=['POST'])
    @endpoint()
    def logout(self):
        request.session.logout(keep_db=True)
        return {'signed_out': True}

    @_r('/me')
    @endpoint()
    def me(self):
        return _user_dict(request.env.user)

    # ---- rates ----------------------------------------------------------
    @_r('/rates/current')
    @endpoint()
    def rate_current(self):
        Rate = request.env['jewellery.gold.rate']
        try:
            rate = Rate.get_current(request.env.company)
        except UserError:
            return {'rate': None, 'reason': 'no_approved_rate'}
        return {'rate': _rate_dict(rate)}

    @_r('/rates')
    @endpoint()
    def rates(self, limit=20, offset=0, **kw):
        Rate = request.env['jewellery.gold.rate']
        domain = [('company_id', '=', request.env.company.id)]
        recs = Rate.search(domain, limit=_int(limit, 20, 1), offset=_int(offset, 0, 0, 10**9),
                           order='effective_at desc, id desc')
        return {'items': [_rate_dict(r) for r in recs], 'total': Rate.search_count(domain)}

    # ---- pieces ---------------------------------------------------------
    @_r('/pieces')
    @endpoint()
    def pieces(self, q=None, karat=None, on_hand=None, limit=50, offset=0, **kw):
        Lot = request.env['stock.lot']
        domain = [('product_id.is_jewellery', '=', True)]
        if q:
            domain += ['|', '|', ('name', 'ilike', q), ('rfid_tag', 'ilike', q),
                       ('product_id.name', 'ilike', q)]
        if karat:
            domain.append(('karat', '=', str(karat)))
        if on_hand in ('1', 'true', True):
            domain.append(('product_qty', '>', 0))
        recs = Lot.search(domain, limit=_int(limit, 50, 1), offset=_int(offset, 0, 0, 10**9),
                          order='name')
        return {'items': [_piece_dict(l) for l in recs], 'total': Lot.search_count(domain)}

    @_r('/pieces/<int:piece_id>')
    @endpoint()
    def piece(self, piece_id, discount=None, **kw):
        lot = _get('stock.lot', piece_id)
        data = _piece_dict(lot)
        pct = 0.0
        if discount not in (None, ''):
            try:
                pct = float(discount)
            except ValueError:
                raise ApiError(400, 'invalid', 'discount must be a number (percent of making).')
        try:
            breakdown = lot.get_price_breakdown(making_discount_pct=pct)
        except (UserError, ValidationError) as e:
            data['breakdown'] = None
            data['breakdown_unavailable'] = str(e.args[0]) if e.args else 'unavailable'
        else:
            rate = request.env['jewellery.gold.rate'].browse(breakdown['rate_id'])
            data['breakdown'] = breakdown
            data['breakdown']['making_discount_pct'] = pct
            data['rate'] = _rate_dict(rate)
        data['memos'] = [_memo_dict(m) for m in request.env['jewellery.approval.memo'].search(
            [('lot_ids', 'in', lot.id)], order='date_out desc')]
        return data

    # ---- clients --------------------------------------------------------
    @_r('/clients')
    @endpoint()
    def clients(self, q=None, tier=None, limit=50, offset=0, **kw):
        Partner = request.env['res.partner']
        # A client is a partner who has been placed in a tier or has bought.
        domain = list(CLIENT_DOMAIN)
        if q:
            domain = ['&'] + domain + ['|', ('name', 'ilike', q), ('email', 'ilike', q)]
        if tier:
            domain = ['&', ('jewellery_tier', '=', tier)] + domain
        recs = Partner.search(domain, limit=_int(limit, 50, 1), offset=_int(offset, 0, 0, 10**9),
                              order='name')
        return {'items': [_client_dict(p) for p in recs], 'total': Partner.search_count(domain)}

    @_r('/clients/<int:partner_id>')
    @endpoint()
    def client(self, partner_id, **kw):
        partner = _get('res.partner', partner_id)
        data = _client_dict(partner, detail=True)
        Sale = request.env['sale.order']
        data['orders'] = [_order_dict(o) for o in Sale.search(
            [('partner_id', '=', partner.id)], order='date_order desc', limit=20)]
        return data

    # ---- sales documents ------------------------------------------------
    @_r('/sales/quotes')
    @endpoint()
    def quotes(self, limit=50, offset=0, **kw):
        return self._orders(('state', 'in', QUOTE_STATES), limit, offset)

    @_r('/sales/orders')
    @endpoint()
    def orders(self, limit=50, offset=0, **kw):
        return self._orders(('state', 'in', ORDER_STATES), limit, offset)

    def _orders(self, state_clause, limit, offset):
        Sale = request.env['sale.order']
        domain = [state_clause]
        recs = Sale.search(domain, limit=_int(limit, 50, 1), offset=_int(offset, 0, 0, 10**9),
                           order='date_order desc, id desc')
        return {'items': [_order_dict(o) for o in recs], 'total': Sale.search_count(domain)}

    @_r('/sales/orders/<int:order_id>')
    @endpoint()
    def order(self, order_id, **kw):
        return _order_dict(_get('sale.order', order_id), detail=True)

    @_r('/sales/invoices')
    @endpoint()
    def invoices(self, limit=50, offset=0, **kw):
        Move = request.env['account.move']
        domain = [('move_type', 'in', ('out_invoice', 'out_refund'))]
        recs = Move.search(domain, limit=_int(limit, 50, 1), offset=_int(offset, 0, 0, 10**9),
                           order='invoice_date desc, id desc')
        return {'items': [_invoice_dict(m) for m in recs], 'total': Move.search_count(domain)}

    @_r('/sales/invoices/<int:move_id>')
    @endpoint()
    def invoice(self, move_id, **kw):
        return _invoice_dict(_get('account.move', move_id), detail=True)

    # ---- memos, old gold, owner -----------------------------------------
    @_r('/memos')
    @endpoint()
    def memos(self, state=None, **kw):
        Memo = request.env['jewellery.approval.memo']
        domain = [('state', '=', state)] if state else []
        return {'items': [_memo_dict(m) for m in Memo.search(domain, order='return_by, id')]}

    @_r('/old-gold')
    @endpoint()
    def old_gold(self, limit=50, offset=0, **kw):
        Og = request.env['jewellery.old.gold']
        recs = Og.search([], limit=_int(limit, 50, 1), offset=_int(offset, 0, 0, 10**9),
                         order='date desc, id desc')
        return {'items': [_old_gold_dict(x) for x in recs], 'total': Og.search_count([])}

    @_r('/owner/cards')
    @endpoint()
    def owner_cards(self, state='open', **kw):
        Card = request.env['jewellery.owner.card']
        domain = [('state', '=', state)] if state and state != 'all' else []
        return {'items': [_card_dict(c) for c in Card.search(domain)]}

    # ---- today ----------------------------------------------------------
    @_r('/today')
    @endpoint()
    def today(self, **kw):
        """The owner's first screen: one number per thing worth knowing.

        A person with partial rights gets a partial dashboard, not an error:
        each figure is read on its own, and a model this user may not read
        comes back as null. That keeps a counter-staff login useful without
        widening what it can see.
        """
        env = request.env
        company = env.company

        def allowed(fn):
            try:
                with env.cr.savepoint():
                    return fn()
            except AccessError:
                return None

        def rate():
            try:
                return _rate_dict(env['jewellery.gold.rate'].get_current(company))
            except UserError:
                return None

        def on_hand():
            lots = env['stock.lot'].search(
                [('product_id.is_jewellery', '=', True), ('product_qty', '>', 0)])
            return {'count': len(lots), 'value': sum(lots.mapped('jewellery_price'))}

        def orders_month():
            Sale = env['sale.order']
            start = fields.Date.context_today(Sale).replace(day=1)
            recs = Sale.search([('state', 'in', ORDER_STATES),
                                ('date_order', '>=', fields.Datetime.to_string(start))])
            return {'count': len(recs), 'amount': sum(recs.mapped('amount_total'))}

        def unpaid():
            recs = env['account.move'].search([
                ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial'))])
            return {'count': len(recs), 'amount': sum(recs.mapped('amount_residual'))}

        def clients():
            P = env['res.partner']
            return {'total': P.search_count(CLIENT_DOMAIN),
                    'restricted': P.search_count([('jewellery_tier', 'in', ('private', 'royal'))])}

        stock = allowed(on_hand)
        return {
            'rate': allowed(rate),
            'currency': _money(company),
            'pieces_on_hand': stock['count'] if stock else None,
            'stock_value_incl_vat': stock['value'] if stock else None,
            'open_quotes': allowed(lambda: env['sale.order'].search_count(
                [('state', 'in', QUOTE_STATES)])),
            'orders_this_month': allowed(orders_month),
            'invoices_unpaid': allowed(unpaid),
            'memos_out': allowed(lambda: env['jewellery.approval.memo'].search_count(
                [('state', '=', 'out')])),
            'old_gold_pending': allowed(lambda: env['jewellery.old.gold'].search_count(
                [('state', 'in', ('draft', 'to_approve'))])),
            'cards_open': allowed(lambda: env['jewellery.owner.card'].search_count(
                [('state', '=', 'open')])),
            'clients': allowed(clients),
        }
