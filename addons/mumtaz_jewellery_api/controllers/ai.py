"""The agents through the door: /jawhar/v1/ai/*.

Same decorator, same audit, same rule as every other endpoint: a tool runs
as the signed-in user. The command bar, the brief, Layla's two drafts and
the approvals inbox (plan v3 wireframe 29) live here.
"""
from odoo.exceptions import UserError
from odoo.http import Controller, request

from .api import ApiError, _body, _get, _int, _m2o, _r, _tray_dict, endpoint


def _draft_dict(d, detail=False):
    data = {
        'id': d.id, 'name': d.name, 'kind': d.kind, 'agent': d.agent, 'state': d.state,
        'client': _m2o(d.partner_id), 'restricted': d.restricted, 'tray': _m2o(d.tray_id),
        'channel': d.channel, 'subject': d.subject or None, 'owner': _m2o(d.owner_id),
        'model_used': d.model_used, 'consent_ok': d.consent_ok, 'expired': d.expired,
        'expires_at': d.expires_at, 'created_at': d.create_date,
        'approved_by': _m2o(d.approved_by_id), 'approved_at': d.approved_at,
        'reasons': [r for r in (d.reasons or '').split('\n') if r],
        'policy_version': d.policy_version,
    }
    if detail:
        data.update({
            'body': d.body or '', 'body_digest': d.body_digest, 'review_note': d.review_note or None,
            'sources': [s for s in (d.sources or '').split('\n') if s],
            'tray_detail': _tray_dict(d.tray_id, detail=True) if d.tray_id else None,
        })
    return data


def _run_dict(r):
    return {
        'id': r.id, 'at': r.create_date, 'agent': r.agent, 'tool': r.tool, 'level': r.level,
        'user': _m2o(r.user_id), 'client': _m2o(r.partner_id), 'draft': _m2o(r.draft_id),
        'status': r.status, 'reason': r.reason or None, 'model_used': r.model_used,
        'input_tokens': r.input_tokens, 'output_tokens': r.output_tokens, 'duration_ms': r.duration_ms,
        'sources': [s for s in (r.sources or '').split('\n') if s], 'policy_version': r.policy_version,
    }


def _agent():
    return request.env['jewellery.ai.agent']


class JawharAiApi(Controller):

    @_r('/ai/status')
    @endpoint()
    def ai_status(self, **kw):
        return _agent().status()

    @_r('/ai/pause', methods=['POST'])
    @endpoint()
    def ai_pause(self, **kw):
        body = _body()
        try:
            paused = _agent().set_paused(bool(body.get('paused', True)))
        except UserError as exc:
            raise ApiError(403, 'forbidden', str(exc))
        return {'paused': paused}

    @_r('/ai/ask', methods=['POST'])
    @endpoint()
    def ai_ask(self, **kw):
        text = (_body().get('text') or '').strip()
        if not text:
            raise ApiError(400, 'validation', 'Say what you need.')
        out = _agent().ask(text[:300])
        if out.get('brief') and not out['brief'].get('refused'):
            out['brief'] = _brief_dict(out['brief'])
        return out

    @_r('/ai/brief', methods=['POST'])
    @endpoint()
    def ai_brief(self, **kw):
        out = _agent().brief()
        return out if out.get('refused') else _brief_dict(out)

    @_r('/ai/queue')
    @endpoint()
    def ai_queue(self, **kw):
        out = _agent().decisions_queue()
        return out if isinstance(out, dict) else {'items': out}

    @_r('/ai/layla/tray', methods=['POST'])
    @endpoint()
    def ai_layla_tray(self, **kw):
        body = _body()
        partner = _get('res.partner', body.get('client_id') or 0)
        out = _agent().prepare_tray(
            partner, intent=(body.get('intent') or '')[:40] or None,
            budget=float(body.get('budget') or 0) or None, limit=_int(body.get('limit'), 3, 1, 5))
        if out.get('refused'):
            return out
        return {'tray': _tray_dict(out['tray'], detail=True), 'draft': _draft_dict(out['draft'], detail=True),
                'run': _run_dict(out['run'])}

    @_r('/ai/layla/followup', methods=['POST'])
    @endpoint()
    def ai_layla_followup(self, **kw):
        body = _body()
        partner = _get('res.partner', body.get('client_id') or 0)
        channel = body.get('channel') or 'whatsapp'
        if channel not in ('note', 'whatsapp', 'email'):
            raise ApiError(400, 'validation', 'channel must be note, whatsapp or email.')
        out = _agent().draft_followup(partner, note=(body.get('context') or '')[:300] or None, channel=channel)
        if out.get('refused'):
            return out
        return {'draft': _draft_dict(out['draft'], detail=True), 'run': _run_dict(out['run'])}

    # -- the inbox -------------------------------------------------------
    @_r('/ai/drafts')
    @endpoint()
    def ai_drafts(self, **kw):
        state = kw.get('state') or 'pending'
        domain = [] if state == 'all' else [('state', '=', state)]
        recs = request.env['jewellery.ai.draft'].search(domain, order='id desc', limit=_int(kw.get('limit'), 50))
        return {'items': [_draft_dict(d) for d in recs], 'count': len(recs)}

    @_r('/ai/drafts/<int:draft_id>')
    @endpoint()
    def ai_draft(self, draft_id, **kw):
        return _draft_dict(_get('jewellery.ai.draft', draft_id), detail=True)

    @_r('/ai/drafts/<int:draft_id>/approve', methods=['POST'])
    @endpoint()
    def ai_draft_approve(self, draft_id, **kw):
        d = _get('jewellery.ai.draft', draft_id)
        d.action_approve(_body().get('digest'))
        return _draft_dict(d, detail=True)

    @_r('/ai/drafts/<int:draft_id>/return', methods=['POST'])
    @endpoint()
    def ai_draft_return(self, draft_id, **kw):
        d = _get('jewellery.ai.draft', draft_id)
        d.action_return((_body().get('note') or '')[:500] or None)
        return _draft_dict(d, detail=True)

    @_r('/ai/drafts/<int:draft_id>/dismiss', methods=['POST'])
    @endpoint()
    def ai_draft_dismiss(self, draft_id, **kw):
        d = _get('jewellery.ai.draft', draft_id)
        d.action_dismiss()
        return _draft_dict(d, detail=True)

    @_r('/ai/drafts/<int:draft_id>/edit', methods=['POST'])
    @endpoint()
    def ai_draft_edit(self, draft_id, **kw):
        d = _get('jewellery.ai.draft', draft_id)
        body = (_body().get('body') or '').strip()
        if not body:
            raise ApiError(400, 'validation', 'The text cannot be empty.')
        d.action_edit_body(body[:4000])
        return _draft_dict(d, detail=True)

    @_r('/ai/runs')
    @endpoint()
    def ai_runs(self, **kw):
        recs = request.env['jewellery.ai.run'].search([], order='id desc', limit=_int(kw.get('limit'), 30))
        return {'items': [_run_dict(r) for r in recs]}


def _brief_dict(b):
    out = dict(b)
    out['queue'] = [dict(q) for q in b['queue']]
    return out
