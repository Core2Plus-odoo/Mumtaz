import base64
from datetime import timedelta

from odoo import fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c6360000002000001e221bc330000000049454e44ae426082"
))
TOKEN_NOTE = 'SYNTHETIC evidence note'


@tagged('post_install', '-at_install', 'faizy')
class TestFaizyWork(TransactionCase):
    """All data here is synthetic. Nothing is sent to a customer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def mk(login, groups):
            return mail_new_test_user(cls.env, login=login, name=login, groups=groups)

        cls.mashood = mk('w_mashood', 'faizy_ai.group_comms')
        cls.raza = mk('w_raza', 'faizy_core.group_faizy_ops')
        cls.umer = mk('w_umer', 'faizy_core.group_faizy_manager')
        cls.env['ir.config_parameter'].sudo().set_param('faizy_ai.care_user_id', cls.mashood.id)
        cls.env['ir.config_parameter'].sudo().set_param('faizy_ai.ops_user_id', cls.raza.id)
        cls.env['ir.config_parameter'].sudo().set_param('faizy_ai.escalation_user_id', cls.umer.id)
        cls.Template = cls.env['faizy.checklist.template']
        cls.service = cls.env['faizy.service'].search([], limit=1) or cls.env['faizy.service'].create(
            {'name': 'SYNTHETIC service'})
        cls.customer = mk('w_cust', 'base.group_portal')

    # ── helpers ──────────────────────────────────────────────────────────
    def _lead(self, user, **extra):
        vals = {'name': 'SYNTHETIC prospect', 'type': 'opportunity', 'user_id': user.id,
                'partner_name': 'SYNTHETIC Remittance House', 'faizy_prospect_kind': 'organisation',
                'faizy_lead_source': 'facebook'}
        vals.update(extra)
        return self.env['crm.lead'].with_user(user).create(vals)

    def _tick_all(self, checklist, user, gate=None, note=TOKEN_NOTE):
        for line in checklist.line_ids.sorted('sequence'):
            if line.state == 'done' or not line.applicable:
                continue
            if gate and line.gate != gate:
                continue
            if line.restricted:
                continue
            if line.evidence_required:
                line.with_user(user).write({'note': note})
            line.with_user(user).action_done()

    def _ready_for_verify(self, lead, user):
        lead.with_user(user).write({
            'faizy_contact_basis': 'public_business',
            'faizy_evidence_url': 'https://example.invalid/synthetic-%s' % lead.id})
        lead.activity_schedule('mail.mail_activity_data_todo', summary='SYNTHETIC next step',
                               date_deadline=fields.Date.today() + timedelta(days=2), user_id=user.id)

    # ── library ──────────────────────────────────────────────────────────
    def test_library_is_complete_and_versioned(self):
        by_role = {}
        for tpl in self.Template.search([('state', '=', 'released')]):
            self.assertEqual(tpl.version, 1)
            self.assertTrue(tpl.item_ids, tpl.code)
            by_role.setdefault(tpl.role, set()).add(tpl.code)
        self.assertEqual(len(by_role['cx'] - {'weekly_review_cx'}), 5)
        self.assertEqual(len(by_role['ops'] - {'weekly_review_ops'}), 5)
        self.assertTrue({'daily_start', 'daily_end'} <= by_role['any'])
        # Every item explains itself.
        self.assertFalse(self.env['faizy.checklist.template.item'].search([('sop', '=', False)]))

    def test_released_template_cannot_be_edited_only_versioned(self):
        tpl = self.Template._latest('qualified_digital_lead')
        with self.assertRaises(UserError):
            tpl.item_ids[0].write({'name': 'changed'})
        new = tpl.action_new_version()
        v2 = self.Template.browse(new['res_id'])
        self.assertEqual((v2.version, v2.state, tpl.state), (2, 'draft', 'retired'))
        v2.action_release()
        self.assertEqual(self.Template._latest('qualified_digital_lead'), v2)

    # ── attach and idempotence ───────────────────────────────────────────
    def test_starting_twice_returns_the_same_checklist(self):
        lead = self._lead(self.mashood)
        a = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        b = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        self.assertEqual(a.id, b.id)
        self.assertEqual(lead.sudo().checklist_count, 1)
        self.assertEqual(a.res_model, 'crm.lead')
        self.assertTrue(all(not ln.done_by for ln in a.line_ids))

    # ── CRM gates, server side ───────────────────────────────────────────
    def test_cannot_verify_without_evidence_checklist_and_next_action(self):
        lead = self._lead(self.mashood)
        with self.assertRaises(ValidationError) as cm:
            lead.with_user(self.mashood).write({'faizy_prospect_status': 'verified'})
        self.assertIn('evidence', str(cm.exception).lower())
        self._ready_for_verify(lead, self.mashood)
        # Fields are fine now but no checklist exists yet.
        with self.assertRaises(ValidationError) as cm:
            lead.with_user(self.mashood).write({'faizy_prospect_status': 'verified'})
        self.assertIn('start a checklist', str(cm.exception).lower())
        ck = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        with self.assertRaises(ValidationError) as cm:
            lead.with_user(self.mashood).write({'faizy_prospect_status': 'verified'})
        self.assertIn('still needs', str(cm.exception).lower())
        self._tick_all(ck, self.mashood, gate='verify')
        lead.with_user(self.mashood).write({'faizy_prospect_status': 'verified'})
        self.assertEqual(lead.faizy_prospect_status, 'verified')
        self.assertEqual(lead.faizy_verified_by, self.mashood)
        self.assertTrue(lead.faizy_verified_on)

    def test_marking_the_parent_done_cannot_skip_mandatory_steps(self):
        """A kanban drag, an RPC write of stage_id and a status write all meet the same gate."""
        lead = self._lead(self.mashood)
        self._ready_for_verify(lead, self.mashood)
        qualified = self.env.ref('crm.stage_lead2')
        for vals in ({'stage_id': qualified.id}, {'faizy_prospect_status': 'qualified'}):
            with self.assertRaises(ValidationError):
                lead.with_user(self.mashood).write(vals)
        self.assertEqual(lead.faizy_prospect_status, 'research')
        self.assertEqual(lead.stage_id, self.env.ref('crm.stage_lead1'))

    def test_full_path_to_qualified_moves_the_standard_stage(self):
        lead = self._lead(self.mashood)
        self._ready_for_verify(lead, self.mashood)
        ck = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        self._tick_all(ck, self.mashood)
        for status in ('verified', 'contacted', 'engaged', 'qualified'):
            lead.with_user(self.mashood).write({'faizy_prospect_status': status})
        self.assertEqual(lead.stage_id, self.env.ref('crm.stage_lead2'))
        self.assertTrue(lead.faizy_qualified_on)
        self.assertEqual(lead.faizy_originator_id, self.mashood)

    def test_paying_customer_needs_real_customer_evidence(self):
        lead = self._lead(self.mashood)
        self._ready_for_verify(lead, self.mashood)
        ck = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        self._tick_all(ck, self.mashood)
        for status in ('verified', 'contacted', 'engaged', 'qualified', 'trial'):
            lead.with_user(self.mashood).write({'faizy_prospect_status': status})
        with self.assertRaises(ValidationError):
            lead.with_user(self.mashood).write({'faizy_prospect_status': 'paying'})

    def test_individual_needs_a_contact_basis_not_an_organisation_link(self):
        lead = self._lead(self.mashood, faizy_prospect_kind='individual', partner_name=False,
                          faizy_contact_basis='inquiry')
        lead.activity_schedule('mail.mail_activity_data_todo', summary='x',
                               date_deadline=fields.Date.today(), user_id=self.mashood.id)
        ck = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        org_line = ck.line_ids.filtered(lambda ln: ln.condition == 'org')
        self.assertFalse(org_line.applicable)
        with self.assertRaises(UserError):
            org_line.with_user(self.mashood).action_done()
        self._tick_all(ck, self.mashood, gate='verify')
        lead.with_user(self.mashood).write({'faizy_prospect_status': 'verified'})
        self.assertEqual(lead.faizy_prospect_status, 'verified')

    def test_duplicate_is_detected_and_blocks_until_reviewed(self):
        first = self._lead(self.mashood, email_from='synthetic.dup@example.invalid')
        second = self._lead(self.raza, email_from='Synthetic.Dup@Example.Invalid', partner_name='Other name')
        self.assertEqual(second.faizy_duplicate_count, 1)
        self.assertIn(first, second._find_duplicates())
        self._ready_for_verify(second, self.raza)
        ck = second.with_user(self.raza)._checklist_start('qualified_direct_sales_lead')
        self._tick_all(ck, self.raza, gate='verify')
        with self.assertRaises(ValidationError) as cm:
            second.with_user(self.raza).write({'faizy_prospect_status': 'verified'})
        self.assertIn('duplicate', str(cm.exception).lower())
        second.with_user(self.raza).write({'faizy_duplicate_reviewed': True})
        second.with_user(self.raza).write({'faizy_prospect_status': 'verified'})

    def test_new_lead_cannot_start_above_research_candidate(self):
        lead = self._lead(self.mashood, faizy_prospect_status='qualified')
        self.assertEqual(lead.faizy_prospect_status, 'research')

    # ── checklist rules ──────────────────────────────────────────────────
    def test_evidence_is_required_where_the_template_says_so(self):
        lead = self._lead(self.mashood)
        ck = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        line = ck.line_ids.filtered(lambda ln: ln.evidence_required)[:1]
        with self.assertRaises(UserError):
            line.with_user(self.mashood).action_done()
        line.with_user(self.mashood).write({'evidence_url': 'https://example.invalid/e'})
        line.with_user(self.mashood).action_done()
        self.assertEqual((line.state, line.done_by), ('done', self.mashood))
        self.assertTrue(line.done_on)

    def test_a_line_cannot_be_changed_except_through_its_buttons(self):
        lead = self._lead(self.mashood)
        ck = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        with self.assertRaises(AccessError):
            ck.line_ids[0].with_user(self.mashood).write({'state': 'done'})
        with self.assertRaises(AccessError):
            ck.with_user(self.mashood).write({'state': 'approved'})

    def test_restricted_step_needs_a_manager_who_is_not_the_owner(self):
        ck = self.env['faizy.checklist']._start(
            self.Template._latest('campaign_preparation'), owner=self.mashood)
        line = ck.line_ids.filtered('restricted')
        self.assertTrue(line)
        with self.assertRaises(UserError):
            line.with_user(self.mashood).action_done()
        line.with_user(self.umer).action_done()
        self.assertEqual(line.done_by, self.umer)
        # A manager who owns the checklist cannot clear their own restricted step.
        own = self.env['faizy.checklist']._start(
            self.Template._latest('service_readiness'), owner=self.umer)
        with self.assertRaises(UserError):
            own.line_ids.filtered('restricted').with_user(self.umer).action_done()

    def test_ready_approve_reject_reopen_keep_history(self):
        ck = self.env['faizy.checklist']._start(
            self.Template._latest('customer_inquiry_handling'),
            record=self._lead(self.mashood), owner=self.mashood)
        with self.assertRaises(UserError):
            ck.with_user(self.mashood).action_ready()
        self._tick_all(ck, self.mashood)
        ck.with_user(self.mashood).action_ready()
        self.assertEqual(ck.state, 'ready')
        self.assertTrue(ck.activity_ids.filtered(lambda a: a.user_id == self.umer))
        with self.assertRaises(AccessError):  # owner is not a manager
            ck.with_user(self.mashood).action_approve()
        ck.with_user(self.umer)._transition_with_reason('reject', 'Evidence link is broken')
        self.assertEqual((ck.state, ck.reject_count), ('in_progress', 1))
        with self.assertRaises(UserError):
            ck.with_user(self.umer)._transition_with_reason('reject', ' ')
        ck.with_user(self.mashood).action_ready()
        ck.with_user(self.umer).action_approve()
        self.assertEqual((ck.state, ck.reviewer_id), ('approved', self.umer))
        with self.assertRaises(UserError):  # approved is frozen
            ck.line_ids[0].with_user(self.mashood).action_undo()
        ck.with_user(self.umer)._transition_with_reason('reopen', 'Customer changed the request')
        self.assertEqual(ck.state, 'in_progress')
        bodies = ' '.join(ck.message_ids.mapped('body'))
        for text in ('Evidence link is broken', 'Customer changed the request', 'Approved by'):
            self.assertIn(text, bodies)

    def test_manager_cannot_approve_their_own_checklist(self):
        ck = self.env['faizy.checklist']._start(
            self.Template._latest('daily_start'), owner=self.umer, period_key='2099-01-01')
        ck.state = 'ready'
        with self.assertRaises(UserError):
            ck.with_user(self.umer).action_approve()

    def test_block_needs_a_reason_and_escalates(self):
        lead = self._lead(self.raza)
        ck = lead.with_user(self.raza)._checklist_start('qualified_direct_sales_lead')
        with self.assertRaises(UserError):
            ck.with_user(self.raza)._transition_with_reason('block', '')
        ck.with_user(self.raza)._transition_with_reason('block', 'Company cannot be verified')
        self.assertEqual(ck.state, 'blocked')
        self.assertTrue(ck.activity_ids.filtered(lambda a: a.user_id == self.umer))
        with self.assertRaises(UserError):
            ck.line_ids[0].with_user(self.raza).action_done()
        # A blocked checklist also blocks the business action behind it.
        self._ready_for_verify(lead, self.raza)
        with self.assertRaises(ValidationError):
            lead.with_user(self.raza).write({'faizy_prospect_status': 'verified'})
        ck.with_user(self.umer)._transition_with_reason('unblock', 'Documents arrived')
        self.assertEqual(ck.state, 'in_progress')

    # ── recurring checklists ─────────────────────────────────────────────
    def test_periodic_cron_is_idempotent_and_autofills(self):
        start = self.Template._latest('daily_start')
        start.user_ids = [(6, 0, [self.mashood.id])]
        Check = self.env['faizy.checklist']
        Check._cron_periodic()
        Check._cron_periodic()
        Check._cron_periodic()
        mine = Check.search([('template_code', '=', 'daily_start'), ('owner_id', '=', self.mashood.id)])
        self.assertEqual(len(mine), 1)
        # Nothing overdue: the overdue line fills itself, with no one named.
        overdue = mine.line_ids.filtered(lambda ln: ln.auto_key == 'overdue')
        self.assertEqual((overdue.state, overdue.auto_done), ('done', True))
        # Overdue work appears and the line un-fills on refresh.
        self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get_id('res.partner'),
            'res_id': self.env.user.partner_id.id, 'user_id': self.mashood.id,
            'date_deadline': fields.Date.today() - timedelta(days=3), 'summary': 'SYNTHETIC late'})
        mine.action_refresh()
        self.assertEqual(overdue.state, 'todo')
        self.assertIn('1 overdue', overdue.auto_note)
        # Nobody is assigned to the others, so they produce nothing.
        self.assertFalse(Check.search([('template_code', '=', 'weekly_review_ops')]))

    def test_personal_checklists_are_private(self):
        start = self.Template._latest('daily_start')
        mine = self.env['faizy.checklist']._start(start, owner=self.mashood, period_key='2099-02-01')
        self.assertFalse(self.env['faizy.checklist'].with_user(self.raza).search([('id', '=', mine.id)]))
        self.assertTrue(self.env['faizy.checklist'].with_user(self.umer).search([('id', '=', mine.id)]))

    # ── orders: Raza's execution checklist ───────────────────────────────
    def _order(self, **extra):
        vals = {'title': 'SYNTHETIC order', 'partner_id': self.customer.partner_id.id,
                'service_id': self.service.id, 'city': 'Karachi'}
        vals.update(extra)
        return self.env['faizy.order'].create(vals)

    def test_order_assign_and_complete_gates(self):
        order = self._order(state='pending')
        ck = order.with_user(self.raza)._checklist_start('order_assignment_execution')
        worker = self.env['faizy.worker'].create(
            {'name': 'SYNTHETIC worker', 'phone': '+920000000000', 'city': 'karachi'}) \
            if 'faizy.worker' in self.env else False
        if worker:
            order.write({'worker_id': worker.id})
        with self.assertRaises(ValidationError) as cm:
            order.with_user(self.raza).action_assign()
        self.assertIn('still needs', str(cm.exception).lower())
        self._tick_all(ck, self.raza, gate='assign')
        order.with_user(self.raza).action_assign()
        self.assertEqual(order.state, 'assigned')
        order.write({'state': 'in_progress', 'proof_image': PNG})
        # Checklist gate first: completion steps are open.
        with self.assertRaises(ValidationError):
            order.with_user(self.raza).action_complete()
        self._tick_all(ck, self.raza, gate='complete')
        # The existing evidence gate is still in force behind it.
        with self.assertRaises(ValidationError):
            order.with_user(self.raza).action_complete()
        order.with_user(self.raza).action_approve_evidence()
        order.with_user(self.raza).action_complete()
        self.assertEqual(order.state, 'completed')

    def test_receipt_step_only_applies_when_money_was_spent(self):
        free = self._order()
        free_ck = free.with_user(self.raza)._checklist_start('order_assignment_execution')
        self.assertFalse(free_ck.line_ids.filtered(lambda ln: ln.condition == 'purchase').applicable)
        paid = self._order(purchase_value=500)
        paid_ck = paid.with_user(self.raza)._checklist_start('order_assignment_execution')
        self.assertTrue(paid_ck.line_ids.filtered(lambda ln: ln.condition == 'purchase').applicable)

    def test_new_orders_get_a_checklist_only_when_the_switch_is_on(self):
        self.assertFalse(self._order().checklist_ids)
        self.env['ir.config_parameter'].sudo().set_param('faizy.checklist_orders', 'on')
        order = self._order()
        self.assertEqual(order.checklist_ids.owner_id, self.raza)
        self.assertEqual(len(order.checklist_ids), 1)

    def test_switching_enforcement_off_is_possible_and_explicit(self):
        lead = self._lead(self.mashood)
        self.env['ir.config_parameter'].sudo().set_param('faizy.checklist_enforce', 'off')
        lead.with_user(self.mashood).write({'faizy_prospect_status': 'qualified'})
        self.assertEqual(lead.faizy_prospect_status, 'qualified')

    # ── content quality gate on drafts ───────────────────────────────────
    def test_draft_cannot_be_approved_with_open_quality_steps(self):
        agent = self.env['faizy.ai.agent'].search([], limit=1)
        draft = self.env['faizy.ai.draft'].create({
            'subject': 'SYNTHETIC draft', 'kind': 'other', 'body': 'SYNTHETIC body',
            'agent_id': agent.id if agent else False})
        ck = draft.with_user(self.mashood)._checklist_start('content_quality')
        with self.assertRaises(ValidationError):
            draft.with_user(self.umer).action_approve()
        self._tick_all(ck, self.mashood, gate='approve')
        draft.with_user(self.umer).action_approve()
        self.assertNotEqual(draft.state, 'draft')

    # ── routing (off until approved) ─────────────────────────────────────
    def test_lead_routing_is_off_by_default_and_follows_roles_when_on(self):
        plain = self.env['crm.lead'].with_user(self.umer).create(
            {'name': 'SYNTHETIC a', 'type': 'opportunity', 'user_id': self.umer.id,
             'faizy_lead_source': 'facebook'})
        self.assertEqual(plain.user_id, self.umer)
        self.env['ir.config_parameter'].sudo().set_param('faizy.work_route_leads', 'on')
        marketing = self.env['crm.lead'].create(
            {'name': 'SYNTHETIC b', 'type': 'opportunity', 'faizy_lead_source': 'facebook'})
        partner = self.env['crm.lead'].create(
            {'name': 'SYNTHETIC c', 'type': 'opportunity', 'faizy_lead_source': 'embassy'})
        self.assertEqual(marketing.user_id, self.mashood)
        self.assertEqual(partner.user_id, self.raza)
        self.assertEqual(marketing.faizy_originator_id.id, self.env.uid)

    # ── permissions and privacy ──────────────────────────────────────────
    def test_both_employees_have_the_same_crm_standing_and_no_admin(self):
        for user in (self.mashood, self.raza):
            self.assertTrue(user.has_group('sales_team.group_sale_salesman'))
            self.assertFalse(user.has_group('base.group_system'))
            self.assertFalse(user.has_group('faizy_core.group_faizy_manager'))
        lead = self._lead(self.umer)
        self.assertFalse(self.env['crm.lead'].with_user(self.raza).search([('id', '=', lead.id)]))
        with self.assertRaises(AccessError):
            lead.with_user(self.mashood).unlink()

    def test_no_new_access_to_documents_or_money(self):
        doc = self.env['faizy.document'].create(
            {'name': 'SYNTHETIC passport', 'doc_type': 'passport', 'partner_id': self.customer.partner_id.id})
        plain_agent = mail_new_test_user(
            self.env, login='w_plain', name='w_plain', groups='faizy_core.group_faizy_user')
        for model in ('faizy.document', 'faizy.wallet'):
            if model in self.env:
                self.assertEqual(
                    self.env[model].with_user(self.mashood).search_count([]),
                    self.env[model].with_user(plain_agent).search_count([]), model)
        with self.assertRaises(AccessError):  # no accounting rights were added to anyone
            self.env['account.move'].with_user(self.mashood).search_count([])
        with self.assertRaises(AccessError):
            self.env['account.move'].with_user(self.raza).search_count([])
        self.assertEqual(
            self.env['faizy.document'].with_user(self.mashood).search([('id', '=', doc.id)]),
            self.env['faizy.document'].with_user(plain_agent).search([('id', '=', doc.id)]))
        with self.assertRaises(AccessError):
            self.env['faizy.plan'].with_user(self.raza).create({'name': 'x'})

    def test_nothing_in_this_module_messages_a_customer(self):
        before = self.env['faizy.whatsapp.message'].search_count([])
        lead = self._lead(self.mashood)
        self._ready_for_verify(lead, self.mashood)
        ck = lead.with_user(self.mashood)._checklist_start('qualified_digital_lead')
        self._tick_all(ck, self.mashood)
        for status in ('verified', 'contacted', 'engaged', 'qualified'):
            lead.with_user(self.mashood).write({'faizy_prospect_status': status})
        ck.with_user(self.mashood).action_ready()
        self.env['faizy.checklist']._cron_periodic()
        self.assertEqual(self.env['faizy.whatsapp.message'].search_count([]), before)
        self.assertNotEqual(
            self.env['ir.config_parameter'].sudo().get_param('faizy.whatsapp_send_mode'), 'on')

    # ── scorecards ───────────────────────────────────────────────────────
    def test_scorecard_says_insufficient_data_and_baseline(self):
        card = self.env['faizy.work.scorecard'].with_user(self.mashood).create({})
        self.assertEqual(card.user_id, self.mashood)
        self.assertEqual(card.profile, 'cx')
        self.assertEqual(card.total_display, 'Insufficient data')
        self.assertIn('Baseline not started', card.status)
        self.assertIn('Insufficient data', card.report)
        raza_card = self.env['faizy.work.scorecard'].with_user(self.raza).create({})
        self.assertEqual(raza_card.profile, 'ops')

    def test_employee_cannot_open_someone_elses_scorecard(self):
        card = self.env['faizy.work.scorecard'].with_user(self.mashood).create({'user_id': self.raza.id})
        self.assertEqual(card.user_id, self.mashood)  # forced back to self
        card_m = self.env['faizy.work.scorecard'].with_user(self.umer).create({'user_id': self.raza.id})
        self.assertEqual(card_m.user_id, self.raza)

    def test_scorecard_is_computed_from_real_records_and_weights_sum_to_100(self):
        from ..models.scorecard import WEIGHTS
        for profile, comps in WEIGHTS.items():
            self.assertEqual(sum(w for _k, _l, w in comps), 100, profile)
        self.env['ir.config_parameter'].sudo().set_param(
            'faizy.kpi_start', str(fields.Date.today() - timedelta(days=30)))
        today = fields.Date.today()
        leads = [self._lead(self.raza, faizy_verified_on=today, name='SYNTHETIC v%s' % i,
                            partner_name='SYNTHETIC Org %s' % i,
                            faizy_originator_id=self.raza.id) for i in range(12)]
        for lead in leads:
            lead.activity_schedule('mail.mail_activity_data_todo', summary='next',
                                   date_deadline=today + timedelta(days=1), user_id=self.raza.id)
        card = self.env['faizy.work.scorecard'].with_user(self.raza).create({})
        self.assertIn('12 verified prospects (target 12)', card.report)
        self.assertIn('12 of 12 open leads have a next action', card.report)
        self.assertEqual(card.status, 'Live.')
        # Pipeline 50 (12/12 verified, no drafts), conversion 0 (none qualified), discipline 100;
        # service and partner readiness have no data. 70 of 100 weight is available, so the
        # total is the weighted mean of those three only: (35*50 + 25*0 + 10*100) / 70 = 39.
        self.assertEqual(card.total_display, '39 / 100')
        self.assertIn('Insufficient data', card.report)
        # With less than 60 of the weight available the total is withheld.
        for lead in leads:
            lead.write({'faizy_verified_on': today - timedelta(days=40)})
        card2 = self.env['faizy.work.scorecard'].with_user(self.raza).create({})
        self.assertEqual(card2.total_display, 'Insufficient data')

    # ── desks ────────────────────────────────────────────────────────────
    def test_desks_open_and_command_centre_is_manager_only(self):
        desk = self.env['faizy.work.desk'].with_user(self.mashood).create({})
        self.assertIn('Overdue', desk.summary)
        self.assertTrue(desk.with_user(self.mashood).action_my_leads()['res_model'])
        with self.assertRaises(AccessError):
            self.env['faizy.work.command'].with_user(self.mashood).create({})
        cc = self.env['faizy.work.command'].with_user(self.umer).create({})
        self.assertIn('w_mashood', cc.summary)
        self.assertIn('w_raza', cc.summary)
        self.assertIn('OFF', cc.summary)
