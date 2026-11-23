"""Planned work for the FAIZY desks (§25): standard Project, two guards.

Reactive work (an order to assign, a reply to approve) is a mail.activity on
the real record (§21). Planned work (the 30-day plan, the daily routine) is a
standard project.task in a project that belongs to a desk. This file adds the
two things Project does not have: a desk on the project, and "no Done
without evidence" on its tasks. Lead teams pick a salesperson by source.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.project.models.project_task import CLOSED_STATES

FAIZY_ROLES = [('care', 'Customer care desk'), ('ops', 'Operations desk')]


class ProjectProject(models.Model):
    _inherit = 'project.project'

    faizy_role = fields.Selection(
        FAIZY_ROLES, string='FAIZY desk',
        help='Tasks in this project are planned work for that desk: they show on '
             '"My plan today", escalate when overdue, and count on "My desk".')
    faizy_evidence_required = fields.Boolean(
        string='Evidence before Done',
        help='A task cannot be marked Done until a note or an attachment is on it.')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    faizy_escalated = fields.Boolean(readonly=True, copy=False)
    faizy_evidence_count = fields.Integer(compute='_compute_faizy_evidence_count')

    def _faizy_evidence(self):
        """Notes and attachments a person put on the task. The automatic
        'created', 'stage changed' and activity-done messages do not count."""
        self.ensure_one()
        task = self.sudo()
        notes = task.message_ids.filtered(
            lambda m: m.message_type == 'comment'
            and ((m.body and m.body.striptags().strip()) or m.attachment_ids))
        return notes, task.attachment_ids

    @api.depends('message_ids', 'message_ids.attachment_ids')
    def _compute_faizy_evidence_count(self):
        for task in self:
            notes, files = task._faizy_evidence()
            task.faizy_evidence_count = len(notes) + len(files)

    def write(self, vals):
        if vals.get('state') == '1_done':
            for task in self:
                if task.project_id.faizy_evidence_required and not any(task._faizy_evidence()):
                    raise UserError(self.env._(
                        '"%s" needs evidence before it is Done: log a note with what you did, '
                        'or attach the photo, screenshot or file.', task.display_name))
        res = super().write(vals)
        if vals.get('state') in CLOSED_STATES:
            Routing = self.env['faizy.routing']
            for task in self:
                Routing._close(task, ('faizy_ai.act_approve_escalation',),
                               self.env._('Task closed.'))
        return res


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    faizy_lead_sources = fields.Char(
        string='FAIZY lead sources',
        help="Comma-separated codes from the lead's \"How they found us\": facebook, "
             "instagram, website, whatsapp, embassy, walk_in, other. A new lead with one "
             "of these sources and no salesperson goes to this team's leader.")

    def _faizy_source_codes(self):
        self.ensure_one()
        return {s.strip() for s in (self.faizy_lead_sources or '').split(',') if s.strip()}

    @api.model
    def _faizy_team_for_source(self, source):
        if not source:
            return self.browse()
        for team in self.sudo().search([('faizy_lead_sources', '!=', False)], order='sequence, id'):
            if source in team._faizy_source_codes():
                return team
        return self.browse()
