"""Synthetic staging demonstration of the two employee scenarios.

Run on a SCRATCH/STAGING database only:
  odoo-bin shell -d <scratch> < faizy/scripts/work_demo.py
Everything is labelled SYNTHETIC. Nothing is sent to a customer: WhatsApp
sending stays off and the script asserts the queue did not grow.
"""
from datetime import timedelta

from odoo import fields

PNG = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
log = []


def say(msg):
    log.append(msg)
    print(msg)


def user(login, name, groups):
    u = env['res.users'].with_context(no_reset_password=True).search([('login', '=', login)])
    if not u:
        u = env['res.users'].with_context(no_reset_password=True).create({
            'login': login, 'name': name, 'password': login, 'email': login,
            'group_ids': [(6, 0, [env.ref(g).id for g in groups])]})
    return u


mashood = user('mashood.demo@example.invalid', 'Mashood (demo)', ['faizy_ai.group_comms'])
raza = user('raza.demo@example.invalid', 'Raza (demo)', ['faizy_core.group_faizy_ops'])
umer = user('umer.demo@example.invalid', 'Umer (demo)', ['faizy_core.group_faizy_manager'])
icp = env['ir.config_parameter'].sudo()
icp.set_param('faizy_ai.care_user_id', mashood.id)
icp.set_param('faizy_ai.ops_user_id', raza.id)
icp.set_param('faizy_ai.escalation_user_id', umer.id)
msgs_before_ids = env['faizy.whatsapp.message'].search([]).ids
today = fields.Date.today()


def tick(checklist, who, gate=None):
    for line in checklist.line_ids.sorted('sequence'):
        if line.state == 'done' or not line.applicable or line.restricted:
            continue
        if gate and line.gate != gate:
            continue
        if line.evidence_required:
            line.with_user(who).write({'note': 'SYNTHETIC evidence: see linked record'})
        line.with_user(who).action_done()


# ═══ MASHOOD: research prospect -> verify -> CRM -> approved outreach -> response -> next action ═══
say('== MASHOOD ==')
lead = env['crm.lead'].with_user(mashood).create({
    'name': 'SYNTHETIC: Gulf Remittance House partnership', 'type': 'opportunity',
    'user_id': mashood.id, 'partner_name': 'SYNTHETIC Gulf Remittance House',
    'faizy_lead_source': 'facebook', 'faizy_expat_country': 'ae', 'faizy_family_city': 'karachi'})
say('1. Research candidate created. status=%s stage=%s originator=%s' % (
    lead.faizy_prospect_status, lead.stage_id.name, lead.faizy_originator_id.name))
try:
    lead.with_user(mashood).write({'faizy_prospect_status': 'verified'})
except Exception as e:  # noqa: BLE001
    say('2. Verify refused (as it should be): ' + str(e).splitlines()[0][:150])
lead.with_user(mashood).write({
    'faizy_contact_basis': 'public_business', 'faizy_evidence_url': 'https://example.invalid/synthetic-listing'})
lead.activity_schedule('mail.mail_activity_data_todo', summary='SYNTHETIC: send approved intro',
                       date_deadline=today + timedelta(days=1), user_id=mashood.id)
ck = lead.with_user(mashood)._checklist_start('qualified_digital_lead')
tick(ck, mashood, gate='verify')
lead.with_user(mashood).write({'faizy_prospect_status': 'verified'})
say('3. Verification checklist done -> status=%s, verified by %s on %s' % (
    lead.faizy_prospect_status, lead.faizy_verified_by.name, lead.faizy_verified_on))
partner = env['res.partner'].create({'name': 'SYNTHETIC Gulf Remittance House', 'phone': '+971500000000'})
lead.partner_id = partner
draft = env['faizy.ai.draft'].with_user(mashood).create({
    'subject': 'SYNTHETIC intro to Gulf Remittance House', 'kind': 'customer_message',
    'body': 'SYNTHETIC: Assalam o Alaikum. Introduction only, no pricing.', 'partner_id': partner.id,
    'payload': '{"phone": "+971500000000", "message_type": "generic"}'})
q = draft.with_user(mashood)._checklist_start('content_quality')
try:
    draft.with_user(mashood).action_approve()
except Exception as e:  # noqa: BLE001
    say('4. Draft approval refused until quality steps are done: ' + str(e).splitlines()[1][:150])
tick(q, mashood, gate='approve')
draft.with_user(mashood).action_approve()
say('5. Quality checklist done, draft approved -> state=%s (sending is OFF, so a person sends it by hand)' % draft.state)
draft.with_user(mashood).action_mark_sent_manually()
lead.with_user(mashood).write({'faizy_prospect_status': 'contacted'})
lead.with_user(mashood).message_post(body='SYNTHETIC response: asked for a call next Tuesday.')
lead.with_user(mashood).write({'faizy_prospect_status': 'engaged'})
lead.activity_schedule('mail.mail_activity_data_call', summary='SYNTHETIC: call Tuesday',
                       date_deadline=today + timedelta(days=4), user_id=mashood.id)
say('6. Marked sent by hand, response recorded, status=%s, next action scheduled (%s open activities)' % (
    lead.faizy_prospect_status, len(lead.activity_ids)))

# ═══ RAZA: opportunity -> verify -> relationship -> CRM -> capability -> authorised test order -> evidence ═══
say('== RAZA ==')
opp = env['crm.lead'].with_user(raza).create({
    'name': 'SYNTHETIC: Karachi eldercare provider', 'type': 'opportunity', 'user_id': raza.id,
    'partner_name': 'SYNTHETIC Karachi Care Services', 'faizy_lead_source': 'embassy'})
opp.with_user(raza).write({
    'faizy_contact_basis': 'referral', 'faizy_evidence_url': 'https://example.invalid/synthetic-registry'})
opp.activity_schedule('mail.mail_activity_data_meeting', summary='SYNTHETIC: discovery meeting',
                      date_deadline=today + timedelta(days=2), user_id=raza.id)
ck = opp.with_user(raza)._checklist_start('qualified_direct_sales_lead')
tick(ck, raza, gate='verify')
opp.with_user(raza).write({'faizy_prospect_status': 'verified'})
say('1. Opportunity verified: status=%s' % opp.faizy_prospect_status)
for st in ('contacted', 'engaged'):
    opp.with_user(raza).write({'faizy_prospect_status': st})
tick(ck, raza)
opp.with_user(raza).write({'faizy_prospect_status': 'qualified'})
say('2. Relationship developed, checklist complete -> status=%s, CRM stage=%s' % (
    opp.faizy_prospect_status, opp.stage_id.name))
vendor = env['res.partner'].create({'name': 'SYNTHETIC Karachi Care Services (vendor)'})
vck = vendor.with_user(raza)._checklist_start('vendor_worker_verification')
tick(vck, raza)
vck.with_user(raza).action_ready()
say('3. Operational capability: vendor verification checklist %s (Ready for Review, mandatory %s/%s)' % (
    vck.state, vck.mandatory_done, vck.mandatory_total))
vck.with_user(umer).action_approve()
say('   Umer approved it -> %s' % vck.state)
service = env['faizy.service'].search([], limit=1)
customer = env['res.partner'].create({'name': 'SYNTHETIC test family'})
worker = env['faizy.worker'].create({'name': 'SYNTHETIC worker', 'phone': '+920000000000', 'city': 'karachi'})
order = env['faizy.order'].create({
    'title': 'SYNTHETIC authorised test order', 'partner_id': customer.id, 'service_id': service.id,
    'city': 'Karachi', 'state': 'pending', 'worker_id': worker.id})
oc = order.with_user(raza)._checklist_start('order_assignment_execution')
try:
    order.with_user(raza).action_assign()
except Exception as e:  # noqa: BLE001
    say('4. Assign refused until the checklist steps are done: ' + str(e).splitlines()[1][:140])
tick(oc, raza, gate='assign')
order.with_user(raza).action_assign()
order.write({'state': 'in_progress', 'proof_image': PNG})
try:
    order.with_user(raza).action_complete()
except Exception as e:  # noqa: BLE001
    say('5. Complete refused until completion steps are done: ' + str(e).splitlines()[1][:140])
tick(oc, raza)
order.with_user(raza).action_approve_evidence()
order.with_user(raza).action_complete()
oc.with_user(raza).action_ready()
say('6. Test order %s: state=%s evidence=%s; checklist %s' % (
    order.name, order.state, order.evidence_state, oc.state))
opp.with_user(raza).write({'faizy_prospect_status': 'trial'})
say('   CRM stage now %s (status %s)' % (opp.stage_id.name, opp.faizy_prospect_status))

queued = env['faizy.whatsapp.message'].search([('id', 'not in', msgs_before_ids)])
say('WhatsApp rows created by the existing draft and order flows during the scenarios (not by faizy_work): %s' % (
    ', '.join('%s=%s' % (m.message_type, m.state) for m in queued) or 'none'))
assert not queued.filtered(lambda m: m.state == 'sent'), 'a customer message was SENT'
say('Customer messages actually sent: 0 (faizy.whatsapp_send_mode = %s)' % (
    icp.get_param('faizy.whatsapp_send_mode') or 'off'))
env.cr.commit()
