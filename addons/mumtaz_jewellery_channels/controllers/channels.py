"""Channels through the door: the rate feed (drafts only), the web shelf's
publication switches, and requests by channel."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.http import Controller, request

from odoo.addons.mumtaz_jewellery_api.controllers.api import ApiError, _body, _get, _int, _m2o, _r, _rate_dict, endpoint


def _feed():
    Feed = request.env['jewellery.rate.feed']
    return Feed.search([('company_id', '=', request.env.company.id)], limit=1)


def _manager():
    if not request.env.user.has_group('mumtaz_jewellery.group_jewellery_manager'):
        raise AccessError('Only a jewellery manager changes the channels.')


class JawharChannelsApi(Controller):

    @_r('/channels/feed')
    @endpoint()
    def feed(self, **kw):
        f = _feed()
        logs = request.env['jewellery.rate.feed.log'].search([('feed_id', '=', f.id)], limit=_int(kw.get('limit'), 20)) if f else []
        return {'feed': f.feed_dict() if f else None,
                'logs': [{'id': l.id, 'at': l.create_date, 'raw_value': l.raw_value, 'rate_per_gram': l.rate_per_gram,
                          'rate': _rate_dict(l.rate_id) if l.rate_id else None, 'note': l.note or None, 'error': l.error or None} for l in logs],
                'can_configure': request.env.user.has_group('mumtaz_jewellery.group_jewellery_manager')}

    @_r('/channels/feed', methods=['POST'])
    @endpoint()
    def feed_set(self, **kw):
        _manager()
        body = _body()
        vals = {}
        for key in ('name', 'provider', 'url', 'json_path', 'unit'):
            if key in body:
                vals[key] = (body[key] or '')[:300] or False
        if 'fixture_value' in body:
            vals['fixture_value'] = float(body['fixture_value'] or 0)
        if 'min_change_pct' in body:
            vals['min_change_pct'] = float(body['min_change_pct'] or 0)
        if 'active' in body:
            vals['active'] = bool(body['active'])
        if vals.get('provider') and vals['provider'] not in ('fixture', 'json_url'):
            raise ApiError(400, 'validation', 'provider is fixture or json_url.')
        if vals.get('unit') and vals['unit'] not in ('gram_24k', 'ounce_24k'):
            raise ApiError(400, 'validation', 'unit is gram_24k or ounce_24k.')
        f = _feed()
        if f:
            f.write(vals)
        else:
            f = request.env['jewellery.rate.feed'].create(dict(vals, company_id=request.env.company.id))
        return f.feed_dict()

    @_r('/channels/feed/fetch', methods=['POST'])
    @endpoint()
    def feed_fetch(self, **kw):
        _manager()
        f = _feed()
        if not f:
            raise ApiError(400, 'invalid', 'No feed is configured.')
        out = f.action_fetch()
        return {'ok': out['ok'], 'error': out.get('error'), 'raw': out.get('raw'), 'rate_per_gram': out.get('rate_per_gram'),
                'skipped': out.get('skipped'), 'rate': _rate_dict(out['rate']) if out.get('rate') else None, 'feed': f.feed_dict()}

    @_r('/channels/shelf')
    @endpoint()
    def shelf(self, **kw):
        T = request.env['product.template'].search([('is_jewellery', '=', True)], order='name')
        Tray = request.env['jewellery.tray']
        lots_by_tmpl = {}
        for lot in Tray._eligible_lots():
            lots_by_tmpl.setdefault(lot.product_id.product_tmpl_id.id, 0)
            lots_by_tmpl[lot.product_id.product_tmpl_id.id] += 1
        return {'items': [{'id': t.id, 'name': t.name, 'category': t.jewellery_category or None, 'published': t.jewellery_published,
                           'on_shelf': lots_by_tmpl.get(t.id, 0), 'has_photo': bool(t.image_1024)} for t in T],
                'public_count': sum(n for tid, n in lots_by_tmpl.items() if T.browse(tid).jewellery_published)}

    @_r('/channels/shelf/<int:tmpl_id>', methods=['POST'])
    @endpoint()
    def shelf_publish(self, tmpl_id, **kw):
        _manager()
        t = _get('product.template', tmpl_id)
        # A jewellery manager decides what is on the web shelf; the product
        # model's own create/write groups are not the question here.
        t.sudo().jewellery_published = bool(_body().get('published'))
        return {'id': t.id, 'published': t.jewellery_published}

    @_r('/channels/requests')
    @endpoint()
    def requests_by_channel(self, **kw):
        days = _int(kw.get('days'), 30, lo=1, hi=365)
        since = fields.Datetime.now() - timedelta(days=days)
        Req = request.env['jewellery.kiosk.request']
        out = {}
        for ch in ('store', 'web'):
            recs = Req.search([('channel', '=', ch), ('create_date', '>=', since)])
            out[ch] = {'requests': len(recs), 'viewing': len(recs.filtered(lambda r: r.kind == 'viewing')),
                       'delivery': len(recs.filtered(lambda r: r.kind == 'delivery')),
                       'confirmed': len(recs.filtered(lambda r: r.state == 'confirmed')),
                       'latest': [{'id': r.id, 'name': r.name, 'kind': r.kind, 'state': r.state, 'serial': r.serial,
                                   'client': _m2o(r.partner_id), 'at': r.create_date} for r in recs[:5]]}
        return {'days': days, 'channels': out}
