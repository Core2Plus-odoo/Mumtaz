"""Layla's outreach: the occasions coming up, the drafts for them, and the
hand-over to the person who sends. Level C to prepare, level D to hand
over, and the server never sends a message."""
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.mumtaz_jewellery_ai.services import policy


class AgentsOutreach(models.AbstractModel):
    _inherit = 'jewellery.ai.agent'

    def _outreach_days(self):
        try:
            return max(1, int(self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.outreach_days', 45)))
        except (TypeError, ValueError):
            return 45

    def _outreach_channel(self, partner):
        """The channel a person could use: a message only with recorded
        consent, else a call note for the advisor."""
        if partner.may_message and partner.phone:
            return 'whatsapp'
        if partner.may_message and partner.email:
            return 'email'
        return 'note'

    def _can_read(self, rec):
        try:
            rec.check_access('read')
            return True
        except AccessError:
            return False

    def _occasion_drafts(self, occ, year):
        return self.env['jewellery.ai.draft'].sudo().search(
            [('occasion_id', '=', occ.id), ('occasion_year', '=', year), ('state', 'not in', ('dismissed', 'expired'))],
            order='id desc')

    @api.model
    def outreach_upcoming(self, days=None):
        """The occasions inside the window, each with the client's consent
        state, the channel a person could use and the draft, if one exists.
        Read as the signed-in user: a restricted client shows only to those
        who may see her."""
        today = fields.Date.context_today(self)
        days = days or self._outreach_days()
        out = []
        occasions = self._allowed(lambda: self.env['jewellery.occasion'].search([])) or []
        for occ in occasions:
            p = occ.partner_id
            if not self._can_read(p):
                continue
            nxt = occ._next_date(today)
            ahead = (nxt - today).days
            if ahead < 0 or ahead > days:
                continue
            draft = self._occasion_drafts(occ, nxt.year)[:1]
            draft = draft.with_user(self.env.user) if draft and self._can_read(draft.with_user(self.env.user)) else None
            out.append({
                'occasion_id': occ.id, 'kind': occ.kind, 'date': nxt, 'in_days': ahead, 'lead_days': occ.lead_days,
                'due': ahead <= occ.lead_days, 'note': occ.note or None,
                'client': {'id': p.id, 'name': p.display_name, 'tier': p.jewellery_tier, 'restricted': p.jewellery_restricted,
                           'phone': p.phone or None, 'email': p.email or None, 'lang': p.lang or None},
                'consent': p.consent_dict(), 'channel': self._outreach_channel(p),
                'owner': {'id': (p.relationship_manager_id or p.deputy_id).id, 'name': (p.relationship_manager_id or p.deputy_id).name}
                if (p.relationship_manager_id or p.deputy_id) else None,
                'draft': {'id': draft.id, 'name': draft.name, 'state': draft.state, 'channel': draft.channel,
                          'sent_at': draft.sent_at, 'sent_by': draft.sent_by_id.name or None} if draft else None,
            })
        out.sort(key=lambda o: (o['date'], o['client']['name']))
        return out

    @api.model
    def outreach_prepare(self, occasion=None, days=None):
        """Draft the occasion messages due: one per occasion per year, for
        the relationship manager (or deputy) to review. Runs each morning,
        or on demand for one occasion. Level C: nothing is sent."""
        started = time.monotonic()
        refused = self._guard('layla', 'outreach.prepare', started)
        if refused:
            return refused
        today = fields.Date.context_today(self)
        Occ = self.env['jewellery.occasion'].sudo()
        occasions = occasion.sudo() if occasion else Occ.search([])
        prepared, skipped = [], []
        for occ in occasions:
            nxt = occ._next_date(today)
            ahead = (nxt - today).days
            window = days if days is not None else occ.lead_days
            if ahead < 0 or ahead > window:
                skipped.append((occ.id, 'not_due'))
                continue
            if self._occasion_drafts(occ, nxt.year):
                skipped.append((occ.id, 'exists'))
                continue
            p = occ.partner_id
            owner = p.relationship_manager_id or p.deputy_id or self.env.user
            if owner._is_superuser() or owner._is_system():
                owner = self.env.user
            agent = self.with_user(owner) if owner != self.env.user else self
            channel = self._outreach_channel(p)
            out = agent.draft_followup(p, channel=channel)
            if out.get('refused'):
                skipped.append((occ.id, out['refused']))
                continue
            draft = out['draft']
            kind = dict(occ._fields['kind'].selection)[occ.kind]
            draft.sudo().write({
                'kind': 'outreach', 'occasion_id': occ.id, 'occasion_year': nxt.year,
                'subject': _('%(kind)s · %(name)s · %(date)s', kind=kind, name=p.display_name, date=nxt),
                'owner_id': owner.id,
                'reasons': '\n'.join([_('%(kind)s on %(date)s, in %(n)s days', kind=kind, date=nxt, n=ahead)]
                                     + ([_('No recorded consent: a call, not a message')] if channel == 'note' and not p.may_message else [])
                                     + [r for r in (draft.reasons or '').split('\n') if r and not r.lower().startswith(occ.kind)]),
            })
            prepared.append(draft)
        run = self._log('layla', 'outreach.prepare', started,
                        reason='%d prepared, %d skipped' % (len(prepared), len(skipped)),
                        sources=['jewellery.ai.draft#%d' % d.id for d in prepared])
        return {'prepared': prepared, 'count': len(prepared), 'skipped': skipped, 'run': run}

    def outreach_send(self, draft, channel=None, note=None):
        """The hand-over: a person takes the approved text to her own phone
        or mail client. Logged at level D with her name; the server sends
        nothing. The pause does not stop a person from sending what was
        already approved."""
        started = time.monotonic()
        handoff = draft.action_mark_sent(channel=channel, note=note)
        run = self._log('layla', 'outreach.send', started, partner=draft.partner_id, draft=draft,
                        model_used='human', reason=handoff['channel'],
                        sources=['jewellery.ai.draft#%d' % draft.id, 'approved_digest=%s' % (draft.approved_digest or '')[:12]])
        return {'draft': draft, 'handoff': handoff, 'run': run}

    @api.model
    def outreach_log(self, limit=30):
        recs = self.env['jewellery.ai.draft'].search([('state', '=', 'sent')], order='sent_at desc', limit=limit)
        return recs

    # -- the command bar and the chat know about outreach ----------------
    @api.model
    def ask(self, text):
        if policy.classify(text) != 'outreach':
            return super().ask(text)
        started = time.monotonic()
        refused = self._guard('zayan', 'intent.route', started, text=text)
        if refused:
            return refused
        self._log('zayan', 'intent.route', started, text=text, sources=['intent=outreach'])
        out = self.outreach_prepare()
        result = {'intent': 'outreach', 'agent': 'layla', 'client': None}
        if out.get('refused'):
            result.update(refused=out['refused'], message=out['message'])
            return result
        upcoming = self.outreach_upcoming()
        result.update(prepared=out['count'], draft_ids=[d.id for d in out['prepared']], upcoming=len(upcoming),
                      due=len([u for u in upcoming if u['due']]))
        return result

    def _chat_report(self, result, ar):
        if result.get('intent') != 'outreach':
            return super()._chat_report(result, ar)
        n, up, due = result.get('prepared', 0), result.get('upcoming', 0), result.get('due', 0)
        text = (('%s مناسبة خلال الفترة القادمة، %s منها مستحقة الآن. حضّرت %s مسودة جديدة؛ راجعيها، وأنتِ من ترسل.' if ar
                 else '%s occasions are coming up, %s of them due now. I drafted %s new message(s); review them, and you send.')
                % (up, due, n))
        return text, [{'label': 'Outreach', 'to': '/outreach'}]

    @api.model
    def chat(self, agent, messages):
        history = [m for m in (messages or []) if isinstance(m, dict) and m.get('text')]
        last = next((m['text'] for m in reversed(history) if m.get('role') == 'user'), '')
        if policy.classify(last) != 'outreach':
            return super().chat(agent, messages)
        ar = self._lang().startswith('ar')
        out = {'agent': 'layla', 'intent': 'outreach', 'links': [], 'model_used': 'local', 'reply': ''}
        result = self.ask(last)
        if result.get('refused'):
            out.update(reply=result['message'], refused=result['refused'])
            return out
        out['reply'], out['links'] = self._chat_report(result, ar)
        return out

    def _chat_help(self, agent, ar):
        text = super()._chat_help(agent, ar)
        if agent == 'layla':
            text += (' وأحضّر رسائل المناسبات القادمة — «المناسبات القادمة».' if ar
                     else ' I also draft the occasion messages coming up ("upcoming occasions").')
        return text
