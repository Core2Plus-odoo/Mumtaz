"""Outreach: consent decides, occasions drive the drafts, a person sends,
and the server never does."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.mumtaz_jewellery_api.tests.test_api import TestJawharApiSalesHub
from odoo.addons.mumtaz_jewellery_crm.tests.test_tray import TrayCase


class OutreachCase(TrayCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.ai_paused', '0')
        cls.Agent = env['jewellery.ai.agent'].with_user(cls.staff)
        cls.Draft = env['jewellery.ai.draft']
        cls.Run = env['jewellery.ai.run'].sudo()
        today = fields.Date.context_today(env['res.partner'])
        cls.today = today
        cls.client.write({'phone': '+971 50 123 4567', 'email': 'tray.client@example.com'})
        cls.client.with_user(cls.staff).action_record_consent('given', source='in_store', note='Asked at the counter.')
        cls.soon = env['jewellery.occasion'].create({
            'partner_id': cls.client.id, 'kind': 'birthday', 'date': today + timedelta(days=10), 'lead_days': 21})
        cls.far = env['jewellery.occasion'].create({
            'partner_id': cls.client.id, 'kind': 'anniversary', 'date': today + timedelta(days=60), 'lead_days': 21})
        cls.unknown = env['res.partner'].create({
            'name': 'TEST Unknown Consent', 'jewellery_tier': 'standard', 'phone': '+971 50 999 0000'})
        cls.unknown_occ = env['jewellery.occasion'].create({
            'partner_id': cls.unknown.id, 'kind': 'eid', 'date': today + timedelta(days=3), 'lead_days': 21})
        cls.private.write({'phone': '+971 50 777 0000'})
        cls.private_occ = env['jewellery.occasion'].create({
            'partner_id': cls.private.id, 'kind': 'wedding', 'date': today + timedelta(days=5), 'lead_days': 21})

    def runs(self, tool):
        return self.Run.search([('tool', '=', tool)], order='id desc')

    def approve(self, draft, user=None):
        d = draft.with_user(user or self.staff)
        d.action_approve(d.body_digest)
        return d


@tagged('post_install', '-at_install')
class TestConsent(OutreachCase):

    def test_consent_is_recorded_with_who_how_and_when_and_written_to_the_record(self):
        c = self.client
        self.assertEqual(c.marketing_consent, 'given')
        self.assertEqual(c.consent_source, 'in_store')
        self.assertEqual(c.consent_by_id, self.staff)
        self.assertEqual(c.consent_date, self.today)
        self.assertTrue(c.may_message)
        self.assertFalse(c.no_marketing)
        self.assertTrue(any('Marketing consent' in (m.body or '') for m in c.message_ids))

    def test_withdrawn_sets_do_not_contact_and_a_source_is_required(self):
        p = self.unknown.with_user(self.staff)
        with self.assertRaises(UserError):
            p.action_record_consent('given')
        with self.assertRaises(UserError):
            p.action_record_consent('maybe', source='phone')
        p.action_record_consent('withdrawn', source='phone')
        self.assertTrue(p.no_marketing)
        self.assertFalse(p.may_message)
        p.action_record_consent('given', source='form')
        self.assertFalse(p.no_marketing)
        self.assertTrue(p.may_message)


@tagged('post_install', '-at_install')
class TestOutreachPrepare(OutreachCase):

    def test_one_draft_per_occasion_per_year_inside_its_lead_time(self):
        out = self.Agent.outreach_prepare()
        self.assertEqual(out['count'], 3, out['skipped'])
        kinds = {d.occasion_id.kind: d for d in out['prepared']}
        self.assertEqual(set(kinds), {'birthday', 'eid', 'wedding'})
        self.assertIn((self.far.id, 'not_due'), out['skipped'])
        birthday = kinds['birthday']
        self.assertEqual(birthday.kind, 'outreach')
        self.assertEqual(birthday.channel, 'whatsapp')
        self.assertEqual(birthday.occasion_year, (self.today + timedelta(days=10)).year)
        self.assertEqual(birthday.owner_id, self.staff)
        self.assertEqual(birthday.state, 'pending')
        self.assertIn('Birthday on', birthday.reasons)
        # the client without recorded consent gets a call note, and the draft says why
        eid = kinds['eid']
        self.assertEqual(eid.channel, 'note')
        self.assertIn('No recorded consent', eid.reasons)
        # the Private client: local path, owned by her relationship manager
        wedding = kinds['wedding']
        self.assertEqual(wedding.model_used, 'local')
        self.assertEqual(wedding.owner_id, self.checker)
        self.assertEqual(wedding.channel, 'note')
        # again: nothing twice
        again = self.Agent.outreach_prepare()
        self.assertEqual(again['count'], 0)
        self.assertIn((self.soon.id, 'exists'), again['skipped'])
        # dismissed: a fresh one may be prepared
        birthday.with_user(self.staff).action_dismiss()
        self.assertEqual(self.Agent.outreach_prepare(occasion=self.soon)['count'], 1)
        run = self.runs('outreach.prepare')[0]
        self.assertEqual(run.level, 'C')
        self.assertIn('prepared', run.reason)

    def test_upcoming_lists_consent_channel_and_draft_and_hides_what_the_person_may_not_see(self):
        self.Agent.outreach_prepare()
        items = self.Agent.outreach_upcoming(days=30)
        names = [i['client']['name'] for i in items]
        self.assertIn('TEST Tray Client', names)
        self.assertIn('TEST Unknown Consent', names)
        self.assertNotIn('TEST Private Client', names)  # staff may not see her
        mine = next(i for i in items if i['client']['name'] == 'TEST Tray Client')
        self.assertEqual(mine['consent']['status'], 'given')
        self.assertEqual(mine['channel'], 'whatsapp')
        self.assertTrue(mine['due'])
        self.assertEqual(mine['draft']['state'], 'pending')
        self.assertEqual(mine['in_days'], 10)
        seen = [i['client']['name'] for i in self.env['jewellery.ai.agent'].with_user(self.checker).outreach_upcoming(days=30)]
        self.assertIn('TEST Private Client', seen)

    def test_paused_tenant_prepares_nothing(self):
        self.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.ai_paused', '1')
        out = self.Agent.outreach_prepare()
        self.assertEqual(out['refused'], 'paused')
        self.assertEqual(self.runs('outreach.prepare')[0].status, 'refused')

    def test_the_command_bar_and_the_chat_route_to_outreach(self):
        out = self.Agent.ask('upcoming occasions')
        self.assertEqual(out['intent'], 'outreach')
        self.assertEqual(out['prepared'], 3)
        chat = self.Agent.chat('layla', [{'role': 'user', 'text': 'what occasions are coming up?'}])
        self.assertEqual(chat['intent'], 'outreach')
        self.assertIn('you send', chat['reply'])
        self.assertEqual(chat['links'][0]['to'], '/outreach')


@tagged('post_install', '-at_install')
class TestOutreachSend(OutreachCase):

    def _birthday_draft(self):
        return self.Agent.outreach_prepare(occasion=self.soon)['prepared'][0]

    def test_an_approved_message_is_handed_to_the_person_who_sends_it(self):
        d = self.approve(self._birthday_draft())
        out = self.Agent.outreach_send(d, channel='whatsapp', note='Sent from the shop phone.')
        self.assertEqual(d.state, 'sent')
        self.assertEqual(d.sent_by_id, self.staff)
        self.assertEqual(d.sent_channel, 'whatsapp')
        self.assertTrue(d.sent_at)
        url = out['handoff']['url']
        self.assertTrue(url.startswith('https://wa.me/971501234567?text='))
        self.assertIn('Dear', url)
        run = out['run']
        self.assertEqual((run.tool, run.level, run.model_used, run.status), ('outreach.send', 'D', 'human', 'done'))
        self.assertEqual(run.user_id, self.staff)
        self.assertTrue(any('message sent' in (m.body or '') and 'WhatsApp' in (m.body or '') for m in self.client.message_ids))
        # the server built a link; it sent nothing
        self.assertFalse(self.env['mail.mail'].sudo().search([('recipient_ids', 'in', self.client.ids)]))

    def test_no_recorded_consent_means_no_message_but_a_call_can_be_noted(self):
        d = self.approve(self.Agent.outreach_prepare(occasion=self.unknown_occ)['prepared'][0])
        with self.assertRaises(UserError):
            d.with_user(self.staff).action_mark_sent(channel='whatsapp')
        self.assertEqual(d.state, 'approved')
        handoff = d.with_user(self.staff).action_mark_sent(channel='note', note='Called; she will come Thursday.')
        self.assertIsNone(handoff['url'])
        self.assertEqual(d.state, 'sent')
        self.assertEqual(d.sent_channel, 'note')

    def test_withdrawn_consent_blocks_approval_of_a_message(self):
        d = self._birthday_draft()
        self.client.with_user(self.staff).action_record_consent('withdrawn', source='phone')
        self.assertFalse(d.consent_ok)
        with self.assertRaises(UserError):
            self.approve(d)

    def test_only_an_approved_unchanged_text_is_sent(self):
        d = self._birthday_draft()
        with self.assertRaises(UserError):
            d.with_user(self.staff).action_mark_sent(channel='whatsapp')
        self.approve(d)
        d.with_user(self.staff).action_edit_body(d.body + ' See you Thursday.')
        self.assertEqual(d.state, 'pending')
        with self.assertRaises(UserError):
            d.with_user(self.staff).action_mark_sent(channel='whatsapp')

    def test_a_restricted_client_is_messaged_only_by_her_relationship_manager(self):
        self.private.with_user(self.checker).action_record_consent('given', source='in_store')
        d = self.env['jewellery.ai.agent'].with_user(self.checker).outreach_prepare(occasion=self.private_occ)['prepared'][0]
        self.assertEqual(d.model_used, 'local')
        self.approve(d, user=self.checker)
        self.assertEqual(d.sudo().channel, 'whatsapp')  # consent recorded by her manager
        out = self.env['jewellery.ai.agent'].with_user(self.checker).outreach_send(d.with_user(self.checker), channel='whatsapp')
        self.assertTrue(out['handoff']['url'].startswith('https://wa.me/971507770000'))
        self.assertEqual(d.sudo().state, 'sent')

    def test_the_pause_does_not_stop_a_person_sending_what_was_approved(self):
        d = self.approve(self._birthday_draft())
        self.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.ai_paused', '1')
        out = self.Agent.outreach_send(d, channel='email')
        self.assertTrue(out['handoff']['url'].startswith('mailto:tray.client@example.com'))
        self.assertEqual(d.state, 'sent')


@tagged('post_install', '-at_install')
class TestJawharApiOutreach(TestJawharApiSalesHub):
    """Outreach through the door."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = fields.Date.context_today(cls.env['res.partner'])
        cls.client.write({'phone': '+971 50 123 9999'})
        cls.occ = cls.env['jewellery.occasion'].create({
            'partner_id': cls.client.id, 'kind': 'birthday', 'date': today + timedelta(days=7), 'lead_days': 21})

    def test_consent_then_prepare_approve_and_hand_over(self):
        self.sign_in('api_seller')
        self.assertEqual(self.api('/clients/%d/consent' % self.client.id)['data']['status'], 'unknown')
        err = self.api('/clients/%d/consent' % self.client.id, 'POST', {'status': 'yes'}, status=400)
        self.assertEqual(err['error']['code'], 'validation')
        err = self.api('/clients/%d/consent' % self.client.id, 'POST', {'status': 'given'}, status=400)
        self.assertEqual(err['error']['code'], 'invalid')
        c = self.api('/clients/%d/consent' % self.client.id, 'POST', {'status': 'given', 'source': 'phone', 'note': 'Called her.'})['data']
        self.assertEqual((c['status'], c['source'], c['recorded_by']['name'], c['may_message']), ('given', 'phone', 'TEST Seller', True))

        up = self.api('/outreach/upcoming?days=30')['data']
        mine = next(i for i in up['items'] if i['occasion_id'] == self.occ.id)
        self.assertEqual((mine['channel'], mine['due'], mine['draft']), ('whatsapp', True, None))

        prep = self.api('/outreach/prepare', 'POST', {'occasion_id': self.occ.id})['data']
        self.assertEqual(prep['count'], 1)
        draft = prep['prepared'][0]
        self.assertEqual((draft['kind'], draft['channel'], draft['occasion']['kind']), ('outreach', 'whatsapp', 'birthday'))
        self.assertEqual(self.api('/outreach/prepare', 'POST', {'occasion_id': self.occ.id})['data']['count'], 0)

        # not approved yet: no hand-over
        err = self.api('/outreach/drafts/%d/send' % draft['id'], 'POST', {'channel': 'whatsapp'}, status=400)
        self.assertEqual(err['error']['code'], 'invalid')
        full = self.api('/ai/drafts/%d' % draft['id'])['data']
        self.api('/ai/drafts/%d/approve' % draft['id'], 'POST', {'digest': full['body_digest']})
        ready = self.api('/outreach/drafts?state=approved')['data']
        self.assertIn(draft['id'], [d['id'] for d in ready['items']])
        detail = self.api('/outreach/drafts/%d' % draft['id'])['data']
        self.assertTrue(detail['handoff']['url'].startswith('https://wa.me/971501239999?text='))

        sent = self.api('/outreach/drafts/%d/send' % draft['id'], 'POST', {'channel': 'whatsapp', 'note': 'From my phone.'})['data']
        self.assertEqual(sent['draft']['state'], 'sent')
        self.assertEqual(sent['draft']['sent_by']['name'], 'TEST Seller')
        self.assertEqual(sent['run']['level'], 'D')
        self.assertTrue(sent['handoff']['url'].startswith('https://wa.me/'))
        log = self.api('/outreach/drafts?state=sent')['data']
        self.assertEqual(log['items'][0]['id'], draft['id'])
        up = self.api('/outreach/upcoming?days=30')['data']
        mine = next(i for i in up['items'] if i['occasion_id'] == self.occ.id)
        self.assertEqual(mine['draft']['state'], 'sent')

    def test_the_door_stays_shut_without_sign_in(self):
        self.assertEqual(self.api('/outreach/upcoming', status=401)['error']['code'], 'unauthenticated')
