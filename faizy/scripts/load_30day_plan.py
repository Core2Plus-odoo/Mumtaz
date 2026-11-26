"""Loads the two 30-day registers as standard Project tasks (staging only).

  odoo-bin shell -d <scratch> < faizy/scripts/load_30day_plan.py

Needs the standard Project app. Idempotent: a task is created only when no
task already carries its stable ID in the name. Does nothing in production
and sends nothing. Plan start comes from ir.config_parameter faizy.plan_start
(YYYY-MM-DD) or defaults to the next Monday.
"""
import csv
import pathlib
from datetime import timedelta

from odoo import fields

if 'project.task' not in env:
    print('Project is not installed here; nothing loaded.')
else:
    base = pathlib.Path('/home/claude/mumtaz/faizy/docs/work')
    start_param = env['ir.config_parameter'].sudo().get_param('faizy.plan_start')
    today = fields.Date.today()
    start = fields.Date.to_date(start_param) if start_param else today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    project = env['project.project'].search([('name', '=', 'FAIZY staff work: first 30 days')], limit=1) or \
        env['project.project'].create({'name': 'FAIZY staff work: first 30 days'})
    people = {'Syed Mashood': 'faizy_ai.care_user_id', 'Muhammad Raza': 'faizy_ai.ops_user_id'}
    made = skipped = 0
    for name in ('30day-register-mashood.csv', '30day-register-raza.csv'):
        for row in csv.DictReader((base / name).open()):
            label = '[%s] %s' % (row['id'], row['title'])
            if env['project.task'].search_count([('project_id', '=', project.id), ('name', 'like', '[%s]' % row['id'])]):
                skipped += 1
                continue
            uid = env['ir.config_parameter'].sudo().get_param(people[row['owner']])
            desc = '\n'.join('<p><b>%s:</b> %s</p>' % (k, row[k]) for k in (
                'category', 'source', 'deliverable', 'evidence', 'dependency', 'status', 'next_action'))
            vals = {
                'name': label, 'project_id': project.id, 'description': desc,
                'priority': '1' if row['priority'] == 'High' else '0',
                'date_deadline': start + timedelta(days=int(row['due_day']) - 1),
            }
            if uid and uid.isdigit():
                vals['user_ids'] = [(6, 0, [int(uid)])]
            env['project.task'].create(vals)
            made += 1
    print('plan start %s: %s tasks created, %s already present' % (start, made, skipped))
    env.cr.commit()
