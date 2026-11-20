"""Kiosk requests are prepared work waiting for a person: they join the
decision queue beside owner cards and agent drafts."""
from odoo import _, models


class AgentsKiosk(models.AbstractModel):
    _inherit = 'jewellery.ai.agent'

    def voice_config(self):
        out = super().voice_config()
        aid = self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.voice_agent_noor')
        if aid:
            out['noor'] = aid
        return out

    def _queue(self, limit=6, safe=False):
        items = super()._queue(limit=limit, safe=safe)
        reqs = self._allowed(lambda: self.env['jewellery.kiosk.request'].search(
            [('state', '=', 'requested')], order='id desc', limit=limit)) or []
        for r in reqs:
            items.append({
                'kind': 'request', 'id': r.id, 'priority': 6 if r.kind == 'delivery' else 5,
                'title': _('%(kind)s · %(serial)s', kind=dict(r._fields['kind'].selection)[r.kind], serial=r.serial),
                'detail': _('Kiosk request from %s') % r.client_name if not safe else _('Kiosk request'),
                'next': _('Call back and confirm or decline'), 'owner': 'store',
                'link': {'model': 'jewellery.kiosk.request', 'id': r.id},
            })
        items.sort(key=lambda i: (-i['priority'], i['kind'], -i['id']))
        return items[:limit]
