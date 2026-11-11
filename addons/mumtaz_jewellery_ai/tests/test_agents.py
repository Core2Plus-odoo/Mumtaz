"""Layla and Zayan: what they prepare, what they refuse, what never reaches
a model, and that approval binds to the exact text."""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.mumtaz_jewellery_crm.tests.test_tray import TrayCase
from ..services import policy, provider


class AgentCase(TrayCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Agent = cls.env['jewellery.ai.agent'].with_user(cls.staff)
        cls.Draft = cls.env['jewellery.ai.draft']
        cls.Run = cls.env['jewellery.ai.run'].sudo()
        cls.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.ai_paused', '0')

    def runs(self, tool):
        return self.Run.search([('tool', '=', tool)], order='id desc')

    def refused(self, fn, *args, **kw):
        """Call and expect a refusal: a result that carries the reason and a
        message, and whose log row is on the same cursor as everything else."""
        out = fn(*args, **kw)
        self.assertTrue(out.get('refused'), out)
        return out['message']


@tagged('post_install', '-at_install')
class TestPolicy(TransactionCase):
    """The pure policy, no provider."""

    def test_intent_words_english_and_arabic(self):
        self.assertEqual(policy.classify('Prepare my day'), 'brief')
        self.assertEqual(policy.classify('prepare a tray for Alpha'), 'tray')
        self.assertEqual(policy.classify('draft a follow-up to Bravo about the ring'), 'followup')
        self.assertEqual(policy.classify('ما هو سعر الذهب'), 'rate')
        self.assertEqual(policy.classify('what is waiting for me'), 'queue')
        self.assertEqual(policy.classify('bake a cake'), 'unknown')

    def test_client_hint(self):
        self.assertEqual(policy.client_hint('prepare a tray for Noor Alpha, 22K'), 'Noor Alpha')
        self.assertEqual(policy.client_hint('draft a note to Bravo about the ring'), 'Bravo')
        self.assertIsNone(policy.client_hint('prepare my day'))

    def test_a_model_number_the_tools_did_not_supply_is_caught(self):
        facts = '{"price": 6491.84, "pieces": 3, "rate": 245.8}'
        self.assertTrue(policy.numbers_are_sourced('Three pieces at 6,491.84 on a rate of 245.80.', facts))
        self.assertTrue(policy.numbers_are_sourced('٣ قطع بسعر ٦٬٤٩١٫٨٤', facts))
        self.assertFalse(policy.numbers_are_sourced('Offer her 10% off, so 5,842.66.', facts))
        self.assertTrue(policy.numbers_are_sourced('No numbers here.', facts))

    def test_restricted_never_enters_a_model(self):
        self.assertEqual(policy.may_enter_model({'tier': 'royal'}), 'restricted_client')
        self.assertEqual(policy.may_enter_model({'tier': 'private'}), 'restricted_client')
        self.assertIsNone(policy.may_enter_model({'tier': 'preferred'}))


@tagged('post_install', '-at_install')
class TestLayla(AgentCase):

    def test_tray_prepared_with_reasons_and_a_draft_in_the_inbox(self):
        out = self.Agent.prepare_tray(self.client, intent='wedding')
        tray, draft = out['tray'], out['draft']
        self.assertEqual(tray.state, 'draft')
        self.assertEqual(len(tray.line_ids), 3)
        self.assertTrue(all(l.reasons for l in tray.line_ids))
        self.assertEqual(draft.kind, 'tray')
        self.assertEqual(draft.state, 'pending')
        self.assertEqual(draft.model_used, 'local')
        self.assertIn(tray.line_ids[0].lot_id.name, draft.body)
        run = self.runs('tray.prepare')[:1]
        self.assertEqual((run.status, run.level, run.model_used), ('done', 'C', 'local'))
        self.assertEqual(run.user_id, self.staff)

    def test_royal_client_is_refused_and_the_refusal_is_logged(self):
        royal = self.env['res.partner'].create({
            'name': 'TEST Royal Agent', 'jewellery_tier': 'royal', 'relationship_manager_id': self.staff.id})
        msg = self.refused(self.Agent.prepare_tray, royal)
        self.assertIn('by hand', msg)
        run = self.runs('tray.prepare')[:1]
        self.assertEqual((run.status, run.reason), ('refused', 'restricted_client'))
        self.assertFalse(self.Draft.search([('partner_id', '=', royal.id)]))

    def test_restricted_client_never_reaches_the_provider(self):
        private = self.env['res.partner'].create({
            'name': 'TEST Private Agent', 'jewellery_tier': 'private', 'relationship_manager_id': self.staff.id})

        def never(*a, **k):
            raise AssertionError('a restricted client reached the provider')
        with patch.object(provider, 'configured', return_value=True), patch.object(provider, 'complete', never):
            out = self.Agent.draft_followup(private, note='She liked the bangle')
        self.assertEqual(out['draft'].model_used, 'local')
        self.assertEqual(out['run'].reason, 'restricted_client')
        self.assertIn('TEST', out['draft'].body)

    def test_model_prose_is_used_for_a_standard_client_and_the_payload_has_no_phone(self):
        self.client.write({'phone': '+971500000000', 'email': 'alpha@example.test'})
        seen = {}

        def fake(system, user_text, max_tokens=1024):
            seen['prompt'] = user_text
            return {'text': 'Dear Noor, your selection is ready.', 'model': 'test-model',
                    'input_tokens': 10, 'output_tokens': 5, 'refused': False, 'duration_ms': 1}
        with patch.object(provider, 'configured', return_value=True), patch.object(provider, 'complete', fake):
            out = self.Agent.draft_followup(self.client)
        self.assertEqual(out['draft'].body, 'Dear Noor, your selection is ready.')
        self.assertEqual(out['draft'].model_used, 'test-model')
        self.assertEqual(out['run'].input_tokens, 10)
        self.assertTrue(out['run'].payload_digest)
        self.assertNotIn('+971500000000', seen['prompt'])
        self.assertNotIn('alpha@example.test', seen['prompt'])

    def test_a_model_sentence_with_an_invented_number_is_dropped(self):
        def fake(system, user_text, max_tokens=1024):
            return {'text': 'Dear Noor, we can offer 15% off, so 4,999.', 'model': 'test-model',
                    'input_tokens': 10, 'output_tokens': 5, 'refused': False, 'duration_ms': 1}
        with patch.object(provider, 'configured', return_value=True), patch.object(provider, 'complete', fake):
            out = self.Agent.draft_followup(self.client)
        self.assertNotIn('4,999', out['draft'].body)
        self.assertEqual(out['run'].reason, 'unsourced_number')
        self.assertEqual(out['draft'].model_used, 'test-model')

    def test_no_marketing_client_gets_a_call_note_not_a_message(self):
        self.client.write({'no_marketing': True})
        out = self.Agent.draft_followup(self.client, channel='whatsapp')
        self.assertEqual(out['draft'].channel, 'note')
        self.assertTrue(out['draft'].consent_ok)
        self.assertIn('Call', out['draft'].body)

    def test_approval_binds_to_the_exact_text(self):
        draft = self.Agent.draft_followup(self.client)['draft'].with_user(self.staff)
        stale = draft.body_digest
        draft.action_edit_body(draft.body + ' See you Thursday.')
        self.assertEqual(draft.state, 'pending')
        with self.assertRaises(UserError):
            draft.action_approve(stale)
        draft.action_approve(draft.body_digest)
        self.assertEqual(draft.state, 'approved')
        self.assertEqual(draft.approved_by_id, self.staff)
        # an edit after approval needs review again
        draft.write({'body': 'Changed again.'})
        self.assertEqual(draft.state, 'pending')
        self.assertFalse(draft.approved_by_id)

    def test_a_lapsed_draft_cannot_be_approved(self):
        draft = self.Agent.draft_followup(self.client)['draft']
        draft.sudo().write({'expires_at': fields.Datetime.now() - timedelta(days=1)})
        try:
            draft.with_user(self.staff).action_approve(draft.body_digest)
            self.fail('a lapsed draft was approved')
        except UserError:
            pass
        self.assertEqual(draft.state, 'expired')

    def test_pause_stops_the_agents_and_is_logged(self):
        with self.assertRaises(UserError):
            self.Agent.set_paused(True)   # staff may not
        self.env['jewellery.ai.agent'].with_user(self.maker).set_paused(True)
        self.refused(self.Agent.prepare_tray, self.client)
        self.assertEqual(self.runs('tray.prepare')[:1].reason, 'paused')
        self.env['jewellery.ai.agent'].with_user(self.maker).set_paused(False)
        self.assertTrue(self.Agent.prepare_tray(self.client)['tray'])


@tagged('post_install', '-at_install')
class TestZayan(AgentCase):

    def test_brief_reads_the_engine_and_narrates_locally(self):
        out = self.Agent.brief()
        self.assertEqual(out['narrated_by'], 'local')
        self.assertEqual(out['level'], 'B')
        self.assertEqual(out['figures']['rate']['rate_per_gram'], 245.80)
        self.assertTrue(any('245.8' in s for s in out['sentences']))
        self.assertTrue(out['sources'])
        self.assertEqual(self.runs('brief.prepare')[:1].status, 'done')

    def test_brief_numbers_from_the_model_must_be_sourced(self):
        def fake(system, user_text, max_tokens=1024):
            return {'text': 'Two things first. Sales are up 37% this week.', 'model': 'test-model',
                    'input_tokens': 1, 'output_tokens': 1, 'refused': False, 'duration_ms': 1}
        with patch.object(provider, 'configured', return_value=True), patch.object(provider, 'complete', fake):
            out = self.Agent.brief()
        self.assertFalse(any('37' in s for s in out['sentences']))
        self.assertEqual(self.runs('brief.prepare')[:1].reason, 'unsourced_number')

    def test_queue_lists_cards_and_drafts_for_a_manager_and_drafts_only_for_staff(self):
        self.env['jewellery.owner.card'].create({'kind': 'rate', 'title': 'TEST rate card', 'priority': 9})
        self.Agent.draft_followup(self.client)
        self.assertEqual([q['kind'] for q in self.Agent.decisions_queue()], ['draft'])
        queue = self.env['jewellery.ai.agent'].with_user(self.maker).decisions_queue()
        kinds = [q['kind'] for q in queue]
        self.assertIn('card', kinds)
        self.assertIn('draft', kinds)
        self.assertEqual(queue[0]['title'], 'TEST rate card')

    def test_ask_routes_without_a_model(self):
        self.assertEqual(self.Agent.ask('prepare my day')['intent'], 'brief')
        self.assertEqual(self.Agent.ask('gold rate?')['rate']['rate_per_gram'], 245.80)
        out = self.Agent.ask('prepare a tray for %s' % self.client.name)
        self.assertEqual(out['agent'], 'layla')
        self.assertTrue(out['tray_id'])
        self.assertEqual(self.Agent.ask('prepare a tray')['intent'], 'need_client')
        self.assertIn('message', self.Agent.ask('bake a cake'))
        run = self.runs('intent.route')[:1]
        self.assertEqual(run.model_used, 'local')
        self.assertEqual(run.request_text, 'bake a cake')

    def test_ask_uses_the_model_only_to_classify(self):
        def fake(system, user_text, max_tokens=1024):
            return {'text': '{"intent": "brief", "client": null}', 'model': 'test-model',
                    'input_tokens': 1, 'output_tokens': 1, 'refused': False, 'duration_ms': 1}
        with patch.object(provider, 'configured', return_value=True), patch.object(provider, 'complete', fake):
            out = self.Agent.ask('what should I look at')
        self.assertEqual(out['intent'], 'brief')
        self.assertEqual(self.runs('intent.route')[:1].model_used, 'test-model')


@tagged('post_install', '-at_install')
class TestChat(AgentCase):

    def chat(self, agent, *texts):
        msgs = [{'role': 'user', 'text': t} for t in texts]
        return self.Agent.chat(agent, msgs)

    def test_zayan_answers_a_tool_request_with_links(self):
        out = self.chat('zayan', 'what is the gold rate?')
        self.assertEqual(out['intent'], 'rate')
        self.assertIn('245.8', out['reply'])
        self.assertEqual(out['links'][0]['to'], '/rates')
        self.assertEqual(out['model_used'], 'local')

    def test_layla_prepares_a_tray_from_the_conversation(self):
        out = self.chat('layla', 'hello', 'prepare a tray for %s' % self.client.name)
        self.assertEqual(out['intent'], 'tray')
        self.assertTrue(any(l['to'].startswith('/trays/') for l in out['links']))
        self.assertIn(self.client.name, out['reply'])

    def test_small_talk_without_a_model_gets_the_local_help(self):
        out = self.chat('layla', 'how are you today')
        self.assertEqual(out['intent'], 'unknown')
        self.assertIn('never send', out['reply'])

    def test_model_chat_uses_facts_and_refuses_restricted_clients(self):
        private = self.env['res.partner'].create({
            'name': 'TEST Private Chat', 'jewellery_tier': 'private', 'relationship_manager_id': self.staff.id})
        seen = {}

        def fake(system, user_text, max_tokens=1024):
            seen['prompt'] = user_text
            return {'text': 'Good morning. The rate is 245.8 today.', 'model': 'test-model',
                    'input_tokens': 1, 'output_tokens': 1, 'refused': False, 'duration_ms': 1}
        with patch.object(provider, 'configured', return_value=True), patch.object(provider, 'complete', fake):
            out = self.chat('zayan', 'how are you feeling')
            self.assertEqual(out['model_used'], 'test-model')
            self.assertIn('245.8', out['reply'])
            self.assertIn('FACTS', seen['prompt'])
            out2 = self.chat('zayan', 'tell me about %s' % private.name)
        self.assertEqual(out2.get('refused'), 'restricted_client')
        self.assertNotIn(private.name, seen['prompt'])

    def test_a_model_reply_with_an_invented_number_falls_back(self):
        def fake(system, user_text, max_tokens=1024):
            return {'text': 'Sales will grow 40% if you discount 12%.', 'model': 'test-model',
                    'input_tokens': 1, 'output_tokens': 1, 'refused': False, 'duration_ms': 1}
        with patch.object(provider, 'configured', return_value=True), patch.object(provider, 'complete', fake):
            out = self.chat('zayan', 'any forecast?')
        self.assertNotIn('40%', out['reply'])
        self.assertEqual(out['model_used'], 'local')
