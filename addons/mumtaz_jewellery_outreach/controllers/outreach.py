"""Outreach through the door: /jawhar/v1/outreach/* and the client's
consent. Same decorator, same audit, same rule: everything runs as the
signed-in user, and the server never sends a message."""
from odoo.http import Controller, request

from odoo.addons.mumtaz_jewellery_api.controllers.ai import _draft_dict, _run_dict
from odoo.addons.mumtaz_jewellery_api.controllers.api import ApiError, _body, _get, _int, _m2o, _r, endpoint


def _outreach_draft_dict(d, detail=False):
    data = _draft_dict(d, detail=detail)
    data.update({
        'occasion': {'id': d.occasion_id.id, 'kind': d.occasion_id.kind, 'year': d.occasion_year} if d.occasion_id else None,
        'consent': d.partner_id.consent_dict() if d.partner_id else None,
        'sent_by': _m2o(d.sent_by_id), 'sent_at': d.sent_at, 'sent_channel': d.sent_channel, 'send_note': d.send_note or None,
    })
    return data


def _agent():
    return request.env['jewellery.ai.agent']


class JawharOutreachApi(Controller):

    @_r('/outreach/upcoming')
    @endpoint()
    def outreach_upcoming(self, **kw):
        days = _int(kw.get('days'), 0, lo=0, hi=365) or None
        items = _agent().outreach_upcoming(days=days)
        return {'items': items, 'count': len(items), 'due': len([i for i in items if i['due']])}

    @_r('/outreach/prepare', methods=['POST'])
    @endpoint()
    def outreach_prepare(self, **kw):
        body = _body()
        occ = _get('jewellery.occasion', body['occasion_id']) if body.get('occasion_id') else None
        days = body.get('days')
        out = _agent().outreach_prepare(occasion=occ, days=_int(days, 0, lo=0, hi=365) if days is not None else None)
        if out.get('refused'):
            return out
        return {'prepared': [_outreach_draft_dict(d) for d in out['prepared']], 'count': out['count'],
                'skipped': [{'occasion_id': i, 'why': w} for i, w in out['skipped']], 'run': _run_dict(out['run'])}

    @_r('/outreach/drafts')
    @endpoint()
    def outreach_drafts(self, **kw):
        state = kw.get('state') or 'approved'
        domain = [('kind', 'in', ('followup', 'outreach'))] + ([] if state == 'all' else [('state', '=', state)])
        order = 'sent_at desc, id desc' if state == 'sent' else 'id desc'
        recs = request.env['jewellery.ai.draft'].search(domain, order=order, limit=_int(kw.get('limit'), 50))
        return {'items': [_outreach_draft_dict(d) for d in recs], 'count': len(recs)}

    @_r('/outreach/drafts/<int:draft_id>')
    @endpoint()
    def outreach_draft(self, draft_id, **kw):
        d = _get('jewellery.ai.draft', draft_id)
        data = _outreach_draft_dict(d, detail=True)
        data['handoff'] = d.handoff(d.channel) if d.state == 'approved' and d.consent_ok else None
        return data

    @_r('/outreach/drafts/<int:draft_id>/send', methods=['POST'])
    @endpoint()
    def outreach_send(self, draft_id, **kw):
        d = _get('jewellery.ai.draft', draft_id)
        body = _body()
        channel = body.get('channel') or d.channel
        if channel not in ('note', 'whatsapp', 'email'):
            raise ApiError(400, 'validation', 'channel must be note, whatsapp or email.')
        out = _agent().outreach_send(d, channel=channel, note=(body.get('note') or '')[:200] or None)
        return {'draft': _outreach_draft_dict(out['draft'], detail=True), 'handoff': out['handoff'], 'run': _run_dict(out['run'])}

    @_r('/clients/<int:client_id>/consent')
    @endpoint()
    def client_consent(self, client_id, **kw):
        return _get('res.partner', client_id).consent_dict()

    @_r('/clients/<int:client_id>/consent', methods=['POST'])
    @endpoint()
    def client_consent_record(self, client_id, **kw):
        p = _get('res.partner', client_id)
        body = _body()
        status = body.get('status')
        if status not in ('given', 'withdrawn', 'unknown'):
            raise ApiError(400, 'validation', 'status must be given, withdrawn or unknown.')
        p.action_record_consent(status, source=body.get('source'), note=(body.get('note') or '')[:200] or None)
        return p.consent_dict()
