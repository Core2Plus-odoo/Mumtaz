"""The 30-day work plan for the two FAIZY executives (§26). Data, not code.

Read by provision_staff.py, which turns it into standard Odoo records: SOP
notes (faizy.ai.knowledge, category Procedure), one project per desk with
"Evidence before Done", and one task per working day per routine, each with
its steps, checklist and the evidence to attach. Six working days a week
(Monday to Saturday), eight productive hours a day: 6.5 h of routine plus a
1.5 h project block that changes with the week's theme. Saturdays carry the
weekly review as a recurring task.

No prices, no counts of customers and no claims appear anywhere in this plan
(decisions §17, §23). Change the plan here, re-run the tool: existing tasks
are kept, missing ones are created.
"""

WORK_HOURS = 8.0
DEADLINE_HOUR_KARACHI = 18   # tasks are due at 18:00 Karachi (13:00 UTC)

# ----------------------------------------------------------------------------- SOPs
SOPS = {
    'SOP-C1 Inbound WhatsApp triage': [
        'Open Care Desk › Inbound to handle. Work oldest first.',
        'Identify the customer and the family member; search the partner before creating one.',
        'Answer through a reply draft (the AI drafts, you approve) or create an order draft for Operations.',
        'Mark each message Handled. Ignore only spam, and say why in a note.',
        'Anything about a complaint, refund or safety goes to Umer as an escalation draft; never answer those alone.',
        'Evidence: a note on the task with the counts (handled, order drafts created, escalated).',
    ],
    'SOP-C2 Reply approval and manual send': [
        'Open Care Desk › Replies awaiting approval.',
        'Check against the knowledge notes: facts, tone, no stale phone number, no prices unless approved.',
        'Approve, or reject with the reason the agent should learn from.',
        'While sending is off: send the approved text from the official WhatsApp phone, then click "Mark as sent '
        'manually".',
        'Only inside 10:00 to 21:00 Karachi.',
        'Evidence: counts approved, rejected and sent by hand, in a note on the task.',
    ],
    'SOP-C3 Completion message and follow-up': [
        'Open Care Desk › My work today › Completion message items.',
        'Confirm Operations approved the proof and receipt.',
        'Tell the customer what was done, when, with the photo; ask if anything else is needed.',
        'Three days later, a short check-in; note the answer on the order.',
        'Evidence: note with the orders messaged and any follow-up booked.',
    ],
    'SOP-C4 Social post of the day (FaizyHaiNa)': [
        'One post a day on the Facebook page, one story on Instagram, from the content calendar.',
        'Allowed content: what Faizy does, how it works, a Faizy at work (with consent), a customer story (with '
        'consent).',
        'Not allowed without written approval: prices, plan numbers, customer counts, follower counts, "free".',
        'Reply to every comment and message on the post within the send window.',
        'Evidence: the post link or a screenshot attached to the task.',
    ],
    'SOP-C5 Digital lead qualification': [
        'Open Care Desk › My leads. New leads from Facebook, Instagram, the website and WhatsApp land on you.',
        'Contact inside 10:00 to 21:00 Karachi. Confirm family city, expat country, the service they need and the '
        'family size.',
        'Fill the Faizy tab on the lead. Move to Qualified when the need and the city are confirmed; mark Lost with '
        'the reason otherwise.',
        'A qualified lead gets a follow-up the next day: plan options that fit, no prices until approved.',
        'Won: create the customer and the first order draft. Hand operational questions to Raza through an order '
        'draft.',
        'Evidence: the lead records themselves plus a note with counts (contacted, qualified, lost).',
    ],
    'SOP-O1 Morning operations review and assignment': [
        'Open Operations Desk › Unassigned orders, Jobs not started, Order drafts.',
        'For each unassigned order: pick a Faizy or vendor active in that city and service, confirm the slot on '
        'WhatsApp, click Assign.',
        'Urgent orders first (escalation is 1 h), then by creation time.',
        'Jobs not started 1 h after their slot: call the Faizy, reschedule or reassign, tell care if the customer '
        'must know.',
        'Evidence: note with counts (assigned, rescheduled, still open and why).',
    ],
    'SOP-O2 Proof and receipt review': [
        'Open Operations Desk › Proof & receipt review.',
        'The photo must show the job done for the right family member; the receipt must match the purchase value.',
        'Approve the evidence, or reject with what must be redone. The customer sees proof only after approval.',
        'Completion without approved evidence is refused by the system; do not ask for exceptions.',
        'Evidence: note with counts (approved, rejected and why).',
    ],
    'SOP-O3 Faizy recruitment and application review': [
        'Open Operations Desk › Applications.',
        'CNIC and photo legible and matching; two references called; city and services recorded.',
        'Approve or reject within 7 days of the application.',
        'Onboarding: documents on file, the service briefing done, the first job shadowed.',
        'Evidence: application records plus a note with calls made.',
    ],
    'SOP-O4 Partner outreach (pharmacies, labs, clinics, embassies)': [
        'Five new contacts a day from the partner target list, by call or WhatsApp.',
        'Create each as a lead with source Embassy Programme, Walk-in / Phone or Other, so it lands in your pipeline.',
        'Say what Faizy does and what a partnership looks like; never quote prices or commissions until approved.',
        'Book a visit or call for interested partners; write the next step and date on the lead.',
        'Evidence: the lead records plus a note with counts (contacted, interested, visits booked).',
    ],
    'SOP-O5 Partner and referral lead qualification': [
        'Open Operations Desk › My leads. Partner, embassy and walk-in leads land on you.',
        'Qualified means: a named contact, a real need or referral flow, and a next step agreed.',
        'Move to Qualified or mark Lost with the reason. Follow-ups are due the next day.',
        'Any agreement draft goes to Umer for approval before it is sent.',
        'Evidence: the lead records plus a note with counts.',
    ],
    'SOP-X1 End-of-day log and evidence rule': [
        'Open My desk (KPIs). Read your waiting, overdue and done numbers.',
        'Every planned task is marked Done only with evidence on it: a note with what was done and the counts, or an '
        'attachment.',
        'Anything overdue: write why on the task, then either finish it or ask Umer to reschedule it.',
        'Log one note on today\'s end-of-day task: the three numbers that mattered and one thing to fix tomorrow.',
    ],
}

# ----------------------------------------------------------------------------- daily routine
# (name, sop, hours, checklist, evidence)
ROUTINE = {
    'care': [
        ('Inbound WhatsApp triage', 'SOP-C1 Inbound WhatsApp triage', 1.0,
         ['Inbound to handle is empty or every item has a next step', 'Escalations sent to Umer where needed'],
         'Note with counts: handled, order drafts, escalated'),
        ('Reply approvals and manual sends', 'SOP-C2 Reply approval and manual send', 1.5,
         ['Replies awaiting approval is empty', 'Every approved reply is sent by hand and marked sent'],
         'Note with counts: approved, rejected, sent'),
        ('Completion messages and customer follow-ups', 'SOP-C3 Completion message and follow-up', 1.0,
         ['Every Completion message item is done', 'Three-day check-ins sent for orders completed three days ago'],
         'Note with orders messaged'),
        ('Social post of the day (FaizyHaiNa)', 'SOP-C4 Social post of the day (FaizyHaiNa)', 1.0,
         ['Post published from the calendar', 'Story published', 'Comments and messages answered'],
         'Post link or screenshot attached'),
        ('Digital lead qualification', 'SOP-C5 Digital lead qualification', 1.5,
         ['Every new lead contacted', 'Leads waiting on me is empty or has a dated next step', 'Faizy tab filled'],
         'Note with counts: contacted, qualified, lost'),
        ('End-of-day log and KPIs', 'SOP-X1 End-of-day log and evidence rule', 0.5,
         ['My desk reviewed', 'Overdue items explained', 'Tomorrow\'s one fix written'],
         'Note with the three numbers and the fix'),
    ],
    'ops': [
        ('Morning operations review', 'SOP-O1 Morning operations review and assignment', 0.75,
         ['Unassigned orders reviewed', 'Jobs not started called', 'Order drafts approved or rejected'],
         'Note with counts'),
        ('Assign and coordinate Faizies for the day', 'SOP-O1 Morning operations review and assignment', 1.25,
         ['Every order for today has a Faizy or vendor', 'Slots confirmed on WhatsApp'],
         'Note with assignments'),
        ('Proof and receipt review', 'SOP-O2 Proof and receipt review', 1.0,
         ['Proof & receipt review is empty', 'Rejections carry the reason'],
         'Note with counts: approved, rejected'),
        ('Partner outreach: five new contacts', 'SOP-O4 Partner outreach (pharmacies, labs, clinics, embassies)', 1.5,
         ['Five contacts made', 'Each is a lead with the right source', 'Next step dated on interested ones'],
         'Note with counts: contacted, interested, visits booked'),
        ('Partner and referral lead qualification', 'SOP-O5 Partner and referral lead qualification', 1.0,
         ['Leads waiting on me is empty or has a dated next step', 'Agreements routed to Umer'],
         'Note with counts'),
        ('Faizy recruitment and applications', 'SOP-O3 Faizy recruitment and application review', 0.5,
         ['New applications reviewed', 'Reference calls made'],
         'Note with calls made'),
        ('End-of-day ops log and KPIs', 'SOP-X1 End-of-day log and evidence rule', 0.5,
         ['My desk reviewed', 'Overdue items explained', 'Tomorrow\'s one fix written'],
         'Note with the three numbers and the fix'),
    ],
}

# ----------------------------------------------------------------------------- project blocks
# Week themes. One 1.5 h block per working day, Monday to Friday; Saturday is the
# weekly review (recurring). (name, checklist, evidence)
WEEKLY_REVIEW = ('Weekly review and next-week plan',
                 ['My desk numbers for the week written down', 'Overdue tasks closed or rescheduled with Umer',
                  'Next week\'s project blocks confirmed', 'One process fix proposed'],
                 'Note with the week\'s numbers and the fix')

BLOCKS = {
    'care': {
        1: [('Read all SOPs and confirm desk access',
             ['Every SOP-C and SOP-X1 read', 'Care Desk, My leads and My desk open without error',
              'Questions sent to Umer'],
             'Note: "read and understood" plus questions'),
            ('Audit the FaizyHaiNa page and Instagram profile',
             ['Bio, link and pinned post reviewed', 'Anything with a price, count or "free" listed for removal',
              'Fixes proposed to Umer'],
             'Screenshots before, list of fixes'),
            ('Reply templates in Knowledge (five)',
             ['Welcome, how-it-works, what-happens-next, proof-delivered, follow-up', 'No prices, no counts',
              'Category: Reply or post template'],
             'The five knowledge notes'),
            ('Content calendar, weeks 1 and 2 (twelve posts)',
             ['One post per working day', 'Each post has a topic, format and a consent check',
              'Sent to Umer for approval'],
             'The calendar attached'),
            ('Diaspora communities list (thirty)',
             ['UAE, Saudi Arabia, UK and US groups and pages', 'Posting rules noted for each',
              'Stored as a note in Knowledge'],
             'The list attached or in Knowledge')],
        2: [('Customer welcome sequence (three messages)',
             ['Day 0, day 3, day 10 messages drafted', 'No prices, no "free"', 'Approved by Umer before use'],
             'The three drafts'),
            ('Post in five diaspora communities',
             ['Rules of each group respected', 'Leads created for every reply', 'Comments answered'],
             'Links or screenshots'),
            ('Testimonial requests to five completed-order customers',
             ['Consent asked before anything is published', 'Replies recorded on the partner'],
             'Note with who was asked and who agreed'),
            ('Content calendar, weeks 3 and 4',
             ['Twelve posts', 'Sent to Umer for approval'],
             'The calendar attached'),
            ('Instagram reels plan (three scripts)',
             ['A Faizy at work, how it works, a family story', 'Consent and no-claims check'],
             'The scripts attached')],
        3: [('Re-engage ten quiet customers',
             ['Customers gone quiet (Command Centre › Operations health) listed',
              'Ten contacted through approved drafts', 'Answers noted'],
             'Note with who answered and what they need'),
            ('FAQ note from the top ten inbound questions',
             ['Questions counted from Inbound', 'Answers checked with Raza where operational', 'Stored in Knowledge'],
             'The knowledge note'),
            ('Post in five diaspora communities', ['As in week 2'], 'Links or screenshots'),
            ('Lead source review in the pipeline',
             ['Which sources produced qualified leads this month', 'Which produced lost leads and why'],
             'Note with the counts per source'),
            ('Referral programme proposal (no figures)',
             ['How a customer refers a family', 'What they get is left blank for Umer to decide'],
             'The proposal attached')],
        4: [('Customer satisfaction check-ins (ten)',
             ['Ten customers with a completed order this month', 'One question: what should we do better?'],
             'Note with the answers'),
            ('Content calendar, month 2', ['Twenty-four posts', 'Sent to Umer'], 'The calendar attached'),
            ('Post in five diaspora communities', ['As in week 2'], 'Links or screenshots'),
            ('Clean the pipeline: lost leads with reasons',
             ['Every lead older than 14 days with no next step is qualified, followed up or marked lost',
              'Lost reasons filled'],
             'Note with counts'),
            ('30-day report and month-2 proposal',
             ['Numbers from My desk and the pipeline', 'What worked, what did not', 'Three proposals for month 2'],
             'The report attached')],
        5: [('Monthly review with Umer',
             ['30-day report presented', 'Month-2 plan agreed'],
             'Note with the decisions')],
    },
    'ops': {
        1: [('Read all SOPs and confirm desk access',
             ['Every SOP-O and SOP-X1 read', 'Operations Desk, My leads and My desk open without error',
              'Questions sent to Umer'],
             'Note: "read and understood" plus questions'),
            ('Verify the Faizy roster',
             ['Every active Faizy: city, services, phone confirmed by call', 'Inactive ones archived with a note'],
             'Note with counts and corrections'),
            ('Partner target list (forty)',
             ['Pharmacies, labs and clinics in Karachi and Lahore', 'Name, contact, area, why them',
              'Stored in Knowledge'],
             'The list attached or in Knowledge'),
            ('Partner one-pager draft (no prices)',
             ['What Faizy does, what the partner does, how a referral flows', 'No commission or price figures',
              'Sent to Umer'],
             'The draft attached'),
            ('Service coverage map',
             ['For each city: services with no active Faizy', 'Recruitment priorities proposed'],
             'The map or table attached')],
        2: [('Post Faizy openings in three channels',
             ['Openings text approved by Umer', 'Applications land in the Applications list'],
             'Links or screenshots'),
            ('Book five partner visits or calls', ['From interested leads',
                                                   'Dates on the leads'], 'Note with the bookings'),
            ('Vendor onboarding checklist in Knowledge',
             ['Documents, service list, how a job is handed over, how a bill is made', 'Category: Procedure'],
             'The knowledge note'),
            ('Escalation drill: one order end to end',
             ['A real or sample order walked from booking to approved proof', 'Every delay and gap written down'],
             'Note with the timeline and gaps'),
            ('Embassy programme contact list (five)',
             ['Five contacts with name and role', 'Each created as a lead with source Embassy Programme'],
             'The lead records')],
        3: [('Partner follow-ups: every qualified partner',
             ['Each qualified partner lead has a dated next step', 'Agreements routed to Umer'],
             'Note with counts'),
            ('Interview three Faizy applicants', ['References called first',
                                                  'Decision recorded on each application'], 'The application records'),
            ('Vendor billing check with Umer (drafts only)',
             ['Vendor bills in draft reviewed with Umer', 'Nothing posted without Umer'],
             'Note with the decisions'),
            ('SLA review: jobs not started and why',
             ['Every "Jobs not started" item this month listed with the reason', 'Two fixes proposed'],
             'Note or table attached'),
            ('Partner pipeline review', ['Stage of every partner lead',
                                         'Lost reasons filled'], 'Note with counts per stage')],
        4: [('Onboard two new Faizies', ['Documents on file', 'Briefing done', 'First job shadowed'], 'Note per Faizy'),
            ('First partner agreement drafts for Umer',
             ['Drafts for partners that asked', 'No figures until Umer fills them'],
             'The drafts attached'),
            ('Operations capacity plan, month 2',
             ['Orders per city per week this month', 'Faizies needed per city', 'Recruitment plan'],
             'The plan attached'),
            ('Clean the pipeline: lost leads with reasons',
             ['Every lead older than 14 days with no next step is qualified, followed up or marked lost'],
             'Note with counts'),
            ('30-day report and month-2 proposal',
             ['Numbers from My desk and the pipeline', 'What worked, what did not', 'Three proposals for month 2'],
             'The report attached')],
        5: [('Monthly review with Umer', ['30-day report presented',
                                          'Month-2 plan agreed'], 'Note with the decisions')],
    },
}

TEAMS = {
    'care': {'name': 'Digital & customer leads (Mashood)',
             'sources': 'facebook, instagram, website, whatsapp'},
    'ops': {'name': 'Partners & referrals (Raza)',
            'sources': 'embassy, walk_in, other'},
}
PROJECTS = {
    'care': 'Mashood · Digital Marketing & Customer Experience · 30-day plan',
    'ops': 'Raza · Business Development & Operations · 30-day plan',
}
STAGES = ['Planned', 'In progress', 'Blocked', 'Done']
