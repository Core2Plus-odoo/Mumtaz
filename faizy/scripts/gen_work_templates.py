#!/usr/bin/env python3
"""Generates faizy_work/data/template_data.xml (the checklist library).

Edit the LIBRARY below, run this script, commit both. Released templates are
immutable in the database, so a wording change ships as a new version number
(bump VERSION for the changed template) and the old version is retired by the
migration, never edited in place.
"""
import pathlib
from xml.sax.saxutils import escape

OUT = pathlib.Path(__file__).resolve().parents[1] / 'odoo/addons/faizy_work/data/template_data.xml'

# item flags: M mandatory (default), O optional, E evidence required,
#             R restricted (Manager, not the owner), c=<cond>, g=<gate>, a=<auto key>
LIBRARY = [
 dict(code='qualified_digital_lead', name='Qualified digital lead', model='crm.lead', kind='record', role='cx',
      desc='Turn a prospect found online into a verified, owned CRM lead with a next step.',
      items=[
  ('Verify the prospect and source', 'Open the source page, post or form. Paste the link under Evidence. Confirm the person or organisation really exists and is the one named.', 'E g=verify'),
  ('Check target-market relevance', 'FAIZY serves overseas Pakistanis and the partners who serve them. Note the family city (Karachi first) and the country they live in.', 'g=qualify'),
  ('Establish a legitimate contact basis', 'Set "Legitimate contact basis" on the Faizy tab: they contacted us, opted in, a public business contact, or a referral. Never use private data taken from a profile.', 'g=verify'),
  ('Identify the customer need or business opportunity', 'Write the need in the customer\'s own words in the notes and pick the service of interest.', 'g=qualify'),
  ('Verify service coverage', 'Check the family city is a covered area and the service exists under Configuration > Services. If not covered, press Block and say why.', 'g=qualify'),
  ('Check for duplicates', 'Use the Possible duplicates link on the Faizy tab. If a record exists, work on it and stop here. Otherwise tick "Duplicates reviewed".', 'g=verify'),
  ('Record CRM owner, next step and follow-up date', 'Set the Salesperson and schedule one activity with a due date that says exactly what happens next.', 'g=verify'),
  ('Organisation: name, source link and verification date', 'Organisation name, evidence link and the date you verified them are filled on the Faizy tab.', 'c=org g=verify'),
 ]),
 dict(code='customer_inquiry_handling', name='Customer inquiry handling', model='crm.lead', kind='record', role='cx',
      desc='Answer a customer inquiry accurately, with approval, and leave a recorded next step.',
      items=[
  ('Review the inquiry history', 'Read the lead\'s chatter and earlier orders so the reply does not repeat or contradict anything.', ''),
  ('Understand the requested service', 'Restate what the customer asked for in the notes. Ask one clear question if it is unclear.', ''),
  ('Check serviceability and approved pricing', 'Confirm the service and city are covered. Plan prices are shown to customers only after Umer approves figures in writing: quote nothing else.', ''),
  ('Prepare an accurate response', 'Draft the reply as an AI draft (Faizy AI > Drafts). Check Roman Urdu spelling and that every fact is true.', ''),
  ('Obtain the required communication approval', 'Link the draft under Evidence. A customer message goes out only after it is approved.', 'E'),
  ('Record whether the response was sent', 'Sending from the app is off: send from the official WhatsApp Business phone, then press "Mark as sent manually" on the draft and link it.', 'E'),
  ('Schedule a follow-up or create an authorised service request', 'Schedule an activity with a due date, or create the order if the customer confirmed.', ''),
 ]),
 dict(code='content_quality', name='Digital media and content quality', model='faizy.ai.draft', kind='record', role='cx',
      desc='Quality gate before a draft or content piece is approved.',
      items=[
  ('Confirm this is the approved content version', 'Compare with the approved script or caption. Do not review an older file.', 'g=approve'),
  ('Verify character and brand consistency', 'Characters match the character bible; the real FAIZY logo is used; no AI likeness of Umer, Raza or Mashood.', 'g=approve'),
  ('Check Urdu and Roman Urdu spelling and language', 'Read it aloud once. Check names, honorifics and numbers.', 'g=approve'),
  ('Review video and audio quality and synchronisation', 'Lip movement, subtitles and voice start together; no clipping or noise.', 'O'),
  ('Verify every factual claim', 'Each service, price or promise is on the approved list. Remove anything unproven.', 'E g=approve'),
  ('Confirm content rights and AI disclosure where required', 'Music, images and voices are licensed or ours. Add the AI label where the rules require it.', 'O'),
  ('Validate captions, call to action, links and platform format', 'Open every link. Check the length and shape for the platform.', 'g=approve'),
  ('Record QA approval or a correction request', 'Write the verdict and what must change in the note.', 'E g=approve'),
  ('Confirm publication only through the authorised workflow', 'Nothing is posted by hand outside the approved schedule.', 'g=approve'),
 ]),
 dict(code='campaign_preparation', name='Marketing campaign preparation', model='none', kind='standalone', role='cx',
      desc='Prepare a campaign. Attach to a Project task when Project is installed.',
      items=[
  ('Define the audience', 'Who exactly, where, in which language. Use real customer questions, not guesses.', ''),
  ('Define the campaign objective', 'One measurable objective, for example verified prospects or booked conversations.', ''),
  ('Verify the offer and service claims', 'Every claim is on the approved list and true today.', 'E'),
  ('Review creatives and the landing experience', 'The page the click lands on says the same thing as the creative.', ''),
  ('Set source and UTM tracking', 'Every link carries the campaign source so leads can be attributed.', ''),
  ('Verify budget authorisation', 'Any spend needs Umer\'s approval. Link or note it.', 'R'),
  ('Prepare the launch checklist', 'Who posts what, when, and who watches replies.', ''),
  ('Record campaign performance and learning', 'After the run: real results and one change for next time.', ''),
 ]),
 dict(code='nurturing_retention', name='Lead nurturing and customer retention', model='crm.lead', kind='record', role='cx',
      desc='Keep a warm lead or customer moving, with real outcomes recorded.',
      items=[
  ('Review the last interaction', 'Read the last message, call note or order.', ''),
  ('Identify the next useful action', 'Pick the one thing that helps the customer next, not a generic nudge.', ''),
  ('Prepare a personalised follow-up', 'Use their name, their city and the service they asked about. Draft it for approval.', ''),
  ('Record objections or feedback', 'Write it as they said it. Do not soften it.', ''),
  ('Confirm the actual customer outcome', 'Did they book, decline or go quiet? Record what really happened.', 'E'),
  ('Schedule the next follow-up if appropriate', 'Set an activity with a date, or close the lead with a reason.', ''),
 ]),
 dict(code='qualified_direct_sales_lead', name='Qualified direct-sales lead', model='crm.lead', kind='record', role='ops',
      desc='Turn a direct-sales prospect into a verified, owned CRM lead with discovery findings.',
      items=[
  ('Verify the company or prospect', 'Confirm the business exists: registration, website or a business listing. Paste the link under Evidence.', 'E g=verify'),
  ('Establish relevance to FAIZY', 'How would this company or person use or sell FAIZY? Write it in one line.', 'g=qualify'),
  ('Identify the business opportunity and decision-making role', 'Who decides, who influences, what would a first service or pilot look like.', 'g=qualify'),
  ('Confirm a legitimate contact channel', 'Set the contact basis on the Faizy tab. Use public business contacts or a referral.', 'g=verify'),
  ('Check for duplicate CRM records', 'Use the Possible duplicates link. If it exists, continue on that record.', 'g=verify'),
  ('Record discovery findings', 'Notes from the conversation: need, timing, volume, objections.', 'g=qualify'),
  ('Assign the next action and due date', 'Schedule one activity with a date.', 'g=verify'),
 ]),
 dict(code='partnership_development', name='Partnership development', model='crm.lead', kind='record', role='ops',
      desc='Develop a partner from first contact to an approved proposal.',
      items=[
  ('Verify the potential partner', 'Registration, track record and references. Link the evidence.', 'E'),
  ('Identify mutual value', 'What the partner gets and what FAIZY gets, in plain words.', ''),
  ('Prepare the discovery agenda', 'Questions about their customers, capacity and service areas.', ''),
  ('Document their requirements', 'Write requirements as they stated them.', ''),
  ('Assess commercial and operational feasibility', 'Can we deliver it in the cities they need, at a cost that works? Use source-backed costs only.', ''),
  ('Draft a proposal using approved terms', 'Use only terms Umer has approved. Do not invent prices or guarantees.', ''),
  ('Obtain approval before any external commitment', 'Umer approves before anything is promised outside FAIZY.', 'R'),
  ('Record the follow-up and CRM stage', 'Update the prospect status and schedule the next action.', ''),
 ]),
 dict(code='vendor_worker_verification', name='Vendor and worker verification', model='res.partner', kind='record', role='ops',
      desc='Verify a vendor before they receive work.',
      items=[
  ('Verify the business or worker information', 'Name, owner, address and a way to reach them. Check against a document or listing.', 'E'),
  ('Confirm location and services', 'Which cities and which services, exactly.', ''),
  ('Record pricing and availability', 'Their price list and hours as they gave them, with the date.', ''),
  ('Check required documentation and references', 'ID, licence if relevant, and at least one reference called.', 'E'),
  ('Assess service reliability and risks', 'Anything that could cause a bad delivery, written plainly.', ''),
  ('Record the verification outcome', 'Verified, verified with conditions, or not verified.', 'E'),
  ('Flag exceptions for review', 'If a check was not possible, press Block and say why.', 'O'),
 ]),
 dict(code='order_assignment_execution', name='Order assignment and execution', model='faizy.order', kind='record', role='ops',
      desc='From a new order to a completed, evidenced one, without skipping the existing gates.',
      items=[
  ('Check the customer\'s requirements', 'Read the description, city, date and any family instructions.', 'g=assign'),
  ('Confirm service availability', 'The service is covered in that city on that date.', 'g=assign'),
  ('Verify the approved pricing and cost', 'Price and any purchase value are the approved ones. Anything else goes to Umer.', 'g=assign'),
  ('Assign a suitable worker or vendor', 'Pick a verified Faizy or vendor and set the field on the order.', 'g=assign'),
  ('Confirm the required timing', 'Worker and customer agree on the time.', 'g=assign'),
  ('Monitor task progress', 'Check in at the agreed time. Note what you learned.', ''),
  ('Record delays or incidents', 'Write what went wrong and what was done. Leave empty only if nothing did.', 'O'),
  ('Review completion evidence', 'Open the proof photo. It must show the finished job. Use Evidence review.', 'E g=complete'),
  ('Verify the itemised receipt', 'Every purchase line matches the receipt and the purchase value.', 'c=purchase g=complete'),
  ('Follow the existing order approval gate', 'Approve the evidence on the order. The order can only complete after approval.', 'E g=complete'),
 ]),
 dict(code='service_readiness', name='Service readiness and unit economics', model='none', kind='standalone', role='ops',
      desc='Decide whether a service is ready to offer. Attach to a Project task when Project is installed.',
      items=[
  ('Verify the actual service scope', 'What is and is not included, in plain words.', ''),
  ('Validate city coverage', 'Which cities, with a named worker or vendor in each.', ''),
  ('Check resource availability', 'Enough workers or vendors for the expected volume.', ''),
  ('Obtain source-backed vendor costs', 'Quotes or receipts, not estimates. Link them.', 'E'),
  ('Calculate the estimated contribution margin', 'Price minus real cost per job. Show the working in the note.', 'E'),
  ('Identify operational risks', 'What could go wrong and how it would be caught.', ''),
  ('Recommend improvements', 'One to three concrete changes.', 'O'),
  ('Submit changes to the service catalogue, pricing or policy for founder approval', 'Nothing changes until Umer approves.', 'R'),
 ]),
 dict(code='daily_start', name='Start of shift', model='none', kind='daily_start', role='any',
      desc='Filled from the ERP where possible. Nothing to report outside it.',
      items=[
  ('Review urgent activities', 'Open My activities and start with what is overdue or due today.', 'a=due_today'),
  ('Review overdue follow-ups', 'Overdue items must be done, moved with a reason, or escalated.', 'a=overdue'),
  ('Review today\'s planned deliverables', 'Check the plan for what is due today.', ''),
  ('Identify blockers', 'Anything that stops you today. Press Block on the affected checklist.', 'a=blocked'),
  ('Confirm today\'s priorities', 'Pick the top three.', ''),
 ]),
 dict(code='daily_end', name='End of shift', model='none', kind='daily_end', role='any',
      desc='Filled from the ERP where possible. No separate end-of-day report.',
      items=[
  ('Confirm completed deliverables and evidence', 'Each finished item has its evidence linked on its own record.', ''),
  ('Review unresolved leads and orders', 'Open leads each have a next action.', 'a=leads_no_next'),
  ('Assign next actions and dates', 'Schedule the activity for anything not finished.', 'a=overdue'),
  ('Record genuine blockers', 'Only real blockers, with the reason.', 'a=blocked'),
  ('Confirm tomorrow\'s priorities', 'Pick the top three for tomorrow.', ''),
 ]),
 dict(code='weekly_review_cx', name='Weekly review: Digital Marketing & CX', model='none', kind='weekly', role='cx',
      desc='Reported separately to the founder.',
      items=[
  ('Verified qualified leads and source performance', 'Which sources produced verified, qualified prospects.', ''),
  ('Sales progress and follow-up compliance', 'Follow-ups done on time versus overdue.', 'a=overdue'),
  ('Customer response performance', 'How quickly and accurately inquiries were answered.', 'a=drafts_waiting'),
  ('Content and campaign quality', 'First-pass approvals and the corrections that came back.', ''),
  ('Actual conversions and customer feedback', 'Real outcomes, in the customers\' words.', ''),
  ('Next week\'s acquisition experiments', 'One or two small tests with a measure for each.', ''),
 ]),
 dict(code='weekly_review_ops', name='Weekly review: BD & Operations', model='none', kind='weekly', role='ops',
      desc='Reported separately to the founder.',
      items=[
  ('Verified direct-sales pipeline', 'Prospects by status, with evidence.', ''),
  ('Prospect meetings and conversions', 'Conversations held and what moved.', ''),
  ('Service coverage and vendor readiness', 'Cities and services with a verified delivery partner.', ''),
  ('Operational exceptions', 'Orders with delays, incidents or evidence exceptions.', 'a=evidence_pending'),
  ('Delivery quality and costs', 'Completed orders with approved evidence and their real cost.', 'a=orders_open'),
  ('Next week\'s business development and operational improvements', 'The few changes that matter most.', ''),
 ]),
]

def flags(fl):
    d = dict(mandatory=True, cond='always', evidence=False, restricted=False, gate='', auto='')
    for tok in fl.split():
        if tok == 'O': d['mandatory'] = False
        elif tok == 'E': d['evidence'] = True
        elif tok == 'R': d['restricted'] = True
        elif tok.startswith('c='): d['cond'] = tok[2:]
        elif tok.startswith('g='): d['gate'] = tok[2:]
        elif tok.startswith('a='): d['auto'] = tok[2:]
        else: raise SystemExit('bad flag ' + tok)
    return d

def main():
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<!-- GENERATED by faizy/scripts/gen_work_templates.py. Do not edit by hand. -->',
           '<odoo noupdate="1">']
    for t in LIBRARY:
        tid = 'tpl_' + t['code']
        out.append(f'    <record id="{tid}" model="faizy.checklist.template">')
        out.append(f'        <field name="name">{escape(t["name"])}</field>')
        out.append(f'        <field name="code">{t["code"]}</field>')
        out.append(f'        <field name="version">1</field>')
        out.append(f'        <field name="res_model">{t["model"]}</field>')
        out.append(f'        <field name="kind">{t["kind"]}</field>')
        out.append(f'        <field name="role">{t["role"]}</field>')
        out.append(f'        <field name="description">{escape(t["desc"])}</field>')
        out.append(f'        <field name="state">released</field>')
        out.append('    </record>')
        for i, (name, sop, fl) in enumerate(t['items'], 1):
            d = flags(fl)
            out.append(f'    <record id="{tid}_i{i:02d}" model="faizy.checklist.template.item">')
            out.append(f'        <field name="template_id" ref="{tid}"/>')
            out.append(f'        <field name="sequence">{i * 10}</field>')
            out.append(f'        <field name="name">{escape(name)}</field>')
            out.append(f'        <field name="sop">{escape(sop)}</field>')
            out.append(f'        <field name="mandatory" eval="{d["mandatory"]}"/>')
            out.append(f'        <field name="condition">{d["cond"]}</field>')
            out.append(f'        <field name="evidence_required" eval="{d["evidence"]}"/>')
            out.append(f'        <field name="restricted" eval="{d["restricted"]}"/>')
            if d['gate']:
                out.append(f'        <field name="gate">{d["gate"]}</field>')
            if d['auto']:
                out.append(f'        <field name="auto_key">{d["auto"]}</field>')
            out.append('    </record>')
    out.append('</odoo>')
    OUT.write_text('\n'.join(out) + '\n')
    print('wrote', OUT, sum(len(t['items']) for t in LIBRARY), 'items,', len(LIBRARY), 'templates')

main()
