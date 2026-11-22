#!/usr/bin/env python3
"""Writes the two 30-day registers (CSV) used by load_30day_plan.py.

Day numbers are offsets from the plan start date the founder chooses
(proposal: Monday 30 Nov 2026, assumption flagged in docs/work/README.md).
Only forward-looking work is listed. Nothing completed is imported.
Targets 15/10 and 12/8/3 are the founder's pilot targets from the brief.
"""
import csv
import pathlib

OUT = pathlib.Path(__file__).resolve().parents[1] / 'docs/work'
COLS = ['id', 'owner', 'category', 'priority', 'title', 'source', 'duration_days', 'start_day', 'due_day',
        'deliverable', 'evidence', 'dependency', 'status', 'next_action']

SRC_BRIEF = 'Staff work brief (23 Nov 2026)'
SRC_AUTO = 'Automation Design BD/Care/Ops (3 Nov 2026)'
SRC_RUN = 'AI Team Operations Runbook (3 Nov 2026)'

MASHOOD = [
 ('M-01', 'Pipeline', 'High', 'Verified prospect pipeline: 15 per week',
  SRC_BRIEF + ' / ' + SRC_AUTO + ' §4', 30, 1, 30,
  '15 verified prospects added per week (weeks 1 to 4), each with owner, evidence link, verification date and next action',
  'CRM leads at status Verified Prospect or higher, with the checklist "Qualified digital lead" complete', 'None',
  'Not started', 'Open the first 3 candidates from public sources and start the checklist on each'),
 ('M-02', 'Pipeline', 'High', 'Outreach drafts: 10 per week for approval',
  SRC_BRIEF, 30, 3, 30,
  '10 outreach drafts per week using approved wording only, no prices; none sent without approval',
  'faizy.ai.draft records linked from the lead; approval recorded', 'M-01 (needs verified prospects)',
  'Not started', 'Draft the first intro for the first verified prospect'),
 ('M-03', 'Customer experience', 'High', 'Inquiry follow-up inside working hours',
  SRC_RUN + ' §2, §5', 30, 1, 30,
  'Every inbound inquiry handled 10:00 to 21:00 Karachi with an approved reply and a recorded next step',
  'Checklist "Customer inquiry handling" per inquiry; drafts approved; no overdue activities', 'None',
  'Not started', 'Open the first inquiry and start its checklist'),
 ('M-04', 'Media quality', 'High', 'Content QA gate on the next five pieces',
  'Rider + Nani NS Publishing Schedule (20 Nov 2026)', 21, 1, 21,
  'Five scheduled pieces pass "Digital media and content quality" before approval',
  'Five approved checklists on the draft or content record; corrections recorded', 'Approved content versions exist',
  'Not started', 'Pick the next scheduled piece and start its quality checklist'),
 ('M-05', 'Pipeline', 'Medium', 'Source tagging audit',
  SRC_AUTO + ' §4a.6', 7, 1, 7,
  'Every call to action opens WhatsApp or the site with a source tag that maps to the lead source field',
  'List of CTAs checked, each with its tag and where the lead lands in CRM', 'None',
  'Not started', 'List every live CTA and its current tag'),
 ('M-06', 'Customer experience', 'Medium', 'Roman Urdu reply library from real inquiries',
  SRC_RUN + ' §5', 14, 3, 17,
  'Up to five real inquiry types with an approved Roman Urdu reply each; no invented prices or promises',
  'Reply drafts approved by Mashood and checked against the approved services list', 'M-03',
  'Not started', 'Group the first real inquiries by type'),
 ('M-07', 'Customer experience', 'Medium', 'Record real customer feedback',
  SRC_AUTO + ' §3 (follow-up)', 30, 7, 30,
  'Feedback and objections from completed orders recorded in CRM as stated; no testimonial used without written consent',
  'CRM notes linked to the order; consent recorded where any quote is to be used', 'First completed real orders',
  'Not started', 'After the next completed order, ask the one follow-up question and record the answer'),
 ('M-08', 'ERP discipline', 'High', 'Sunday weekly review in the ERP',
  SRC_RUN + ' §7', 30, 7, 30,
  'Weekly review checklist completed every Sunday (four times)',
  'Four "Weekly review: Digital Marketing & CX" checklists marked Ready for Review', 'Founder assigns the recurring checklist',
  'Not started', 'Complete the first review on the first Sunday'),
 ('M-09', 'Growth', 'Medium', 'One acquisition experiment each week',
  SRC_BRIEF, 30, 7, 30,
  'One small test per week with a stated measure and the real result recorded',
  'Experiment note on the weekly review checklist with the measured outcome', 'M-05',
  'Not started', 'Write the first experiment and how it will be measured'),
 ('M-10', 'Growth', 'Low', 'Campaign preparation for the next campaign',
  'Campaign checklist (this release)', 14, 14, 30,
  'Campaign brief with audience, objective, verified claims, tracking and budget request',
  'Checklist "Marketing campaign preparation" complete; budget authorisation recorded by Umer', 'M-05; Umer authorises any spend',
  'Not started', 'Start the checklist and write the audience and objective'),
]

RAZA = [
 ('R-01', 'Pipeline', 'High', 'Verified direct-sales and partner prospects: 12 per week',
  SRC_BRIEF + ' / ' + SRC_AUTO + ' §4b', 30, 1, 30,
  '12 verified prospects per week (weeks 1 to 4) from public business sources or referrals',
  'CRM leads at Verified Prospect or higher with the checklist "Qualified direct-sales lead" complete', 'None',
  'Not started', 'Open the first 3 candidates and start the checklist'),
 ('R-02', 'Pipeline', 'High', 'Outreach drafts: 8 per week',
  SRC_BRIEF, 30, 3, 30,
  '8 drafts per week using approved terms; Umer approves any email before it is sent',
  'faizy.ai.draft records linked to the leads; approvals recorded', 'R-01',
  'Not started', 'Draft the first message for the first verified prospect'),
 ('R-03', 'Pipeline', 'Medium', 'Discovery conversations (stretch: 3 per week)',
  SRC_BRIEF, 30, 7, 30,
  'Up to 3 discovery conversations per week with findings recorded; a stretch, not a quota',
  'CRM notes and an Engaged status on the lead; discovery step ticked', 'R-01',
  'Not started', 'Book the first conversation with an engaged prospect'),
 ('R-04', 'Operations', 'High', 'Vendor and worker verification, Karachi first',
  SRC_RUN + ' §3, §5', 30, 1, 30,
  'Each vendor used for repairs or trades is verified before receiving work; outcome recorded',
  'Checklist "Vendor and worker verification" approved on each vendor record', 'None',
  'Not started', 'List current vendors and start the checklist on the first'),
 ('R-05', 'Operations', 'High', 'Manual check of Evidence review and Approve evidence',
  'Production Deploy Record (22 Nov 2026), open item', 3, 1, 3,
  'One real or test order taken through proof upload, Approve evidence and completion by a person',
  'Order shows evidence approved, reviewer and date; screenshots kept', 'Fifth deploy approved by Umer',
  'Not started', 'Open Evidence review and note what is waiting'),
 ('R-06', 'Operations', 'High', 'Order assignment and execution discipline',
  SRC_RUN + ' §3', 30, 1, 30,
  'Every order assigned and completed through its checklist, with proof and itemised receipt approved',
  'Checklist "Order assignment and execution" complete on each order; evidence approved', 'Founder turns on automatic order checklists',
  'Not started', 'Start the checklist on the next new order'),
 ('R-07', 'Operations', 'Medium', 'Service readiness and unit economics, one service at a time',
  'Gap list (22 Nov 2026) / ' + SRC_BRIEF, 30, 7, 30,
  'For each catalogue service: scope, Karachi coverage, source-backed vendor cost and estimated margin; recommendations to Umer',
  'Checklist "Service readiness and unit economics" complete with linked quotes; changes submitted for approval', 'R-04',
  'Not started', 'Pick the first service and collect two source-backed costs'),
 ('R-08', 'ERP discipline', 'Medium', 'Pipeline hygiene review each week',
  SRC_BRIEF, 30, 1, 30,
  'No open lead without a next action; stale leads closed with a reason or moved',
  'Zero open leads without a next action on the end-of-shift checklist', 'None',
  'Not started', 'Review the open leads without a next action'),
 ('R-09', 'Operations', 'Medium', 'Operational exceptions log',
  SRC_BRIEF, 30, 1, 30,
  'Delays, incidents and evidence exceptions recorded on the order with a reason',
  'Order notes and exception reasons; summarised on the weekly review', 'None',
  'Not started', 'Record any delay on the next open order'),
 ('R-10', 'ERP discipline', 'High', 'Sunday weekly review in the ERP',
  SRC_RUN + ' §7', 30, 7, 30,
  'Weekly review checklist completed every Sunday (four times) with one proposed improvement',
  'Four "Weekly review: BD & Operations" checklists marked Ready for Review', 'Founder assigns the recurring checklist',
  'Not started', 'Complete the first review on the first Sunday'),
]


def write(name, owner, rows):
    path = OUT / name
    with path.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        for r in rows:
            rid, cat, prio, title, src, dur, start, due, deliv, evid, dep, status, nxt = r
            w.writerow([rid, owner, cat, prio, title, src, dur, start, due, deliv, evid, dep, status, nxt])
    print('wrote', path, len(rows))


write('30day-register-mashood.csv', 'Syed Mashood', MASHOOD)
write('30day-register-raza.csv', 'Muhammad Raza', RAZA)
