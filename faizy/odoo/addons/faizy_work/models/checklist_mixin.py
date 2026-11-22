from odoo import api, fields, models
from odoo.exceptions import ValidationError

ENFORCE_PARAM = 'faizy.checklist_enforce'      # "off" switches every gate off
AUTO_ORDERS_PARAM = 'faizy.checklist_orders'   # "on": every new order gets the order checklist


class FaizyChecklistMixin(models.AbstractModel):
    """Attaches checklists to a business record. The record stays the source of
    truth: the checklist only records who did which step and where the evidence is."""
    _name = 'faizy.checklist.mixin'
    _description = 'Record that carries FAIZY checklists'

    checklist_ids = fields.One2many(
        'faizy.checklist', 'res_id', string='Checklists',
        domain=lambda self: [('res_model', '=', self._name)])
    checklist_count = fields.Integer(compute='_compute_checklist_summary')
    checklist_summary = fields.Char(compute='_compute_checklist_summary')

    @api.depends('checklist_ids.state', 'checklist_ids.mandatory_done', 'checklist_ids.mandatory_total')
    def _compute_checklist_summary(self):
        for rec in self:
            cks = rec.checklist_ids
            rec.checklist_count = len(cks)
            rec.checklist_summary = ', '.join(
                f'{c.template_id.name}: {c.mandatory_done}/{c.mandatory_total}' for c in cks)

    # ── start ────────────────────────────────────────────────────────────
    def action_start_checklist(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'faizy.checklist.start',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }

    def _checklist_start(self, code, owner=None):
        template = self.env['faizy.checklist.template'].sudo()._latest(code)
        if not template:
            return self.env['faizy.checklist']
        return self.env['faizy.checklist']._start(template, record=self, owner=owner or self.env.user)

    # ── gates ────────────────────────────────────────────────────────────
    @api.model
    def _checklist_enforced(self):
        return not self.env.su and (
            self.env['ir.config_parameter'].sudo().get_param(ENFORCE_PARAM) != 'off')

    def _checklist_gate(self, gate, require_existing=False, what=None):
        """Refuse a business action while mandatory steps behind it are open.
        Server-side: a button, an RPC write or a kanban drag all pass through here."""
        if not self._checklist_enforced():
            return
        problems = []
        for rec in self:
            cks = rec.sudo().checklist_ids
            covering = cks.filtered(lambda c: c.line_ids.filtered(lambda ln: ln.gate == gate))
            if require_existing and not covering:
                tpl = self.env['faizy.checklist.template'].sudo().search([
                    ('res_model', '=', rec._name), ('state', '=', 'released'),
                    ('item_ids.gate', '=', gate)], limit=3)
                problems.append(self.env._(
                    '%(rec)s: start a checklist first (%(tpl)s).',
                    rec=rec.display_name, tpl=', '.join(tpl.mapped('name')) or gate))
                continue
            for ck in covering:
                if ck.state == 'blocked':
                    problems.append(self.env._(
                        '%(rec)s: checklist "%(ck)s" is blocked: %(why)s',
                        rec=rec.display_name, ck=ck.name, why=ck.blocked_reason or ''))
                    continue
                missing = ck._gate_missing(gate)
                if missing:
                    problems.append(self.env._(
                        '%(rec)s: checklist "%(ck)s" still needs: %(m)s',
                        rec=rec.display_name, ck=ck.name, m='; '.join(missing)))
        if problems:
            raise ValidationError(self.env._(
                'Cannot %(what)s yet.\n%(p)s', what=what or gate, p='\n'.join(problems)))


class FaizyChecklistStart(models.TransientModel):
    _name = 'faizy.checklist.start'
    _description = 'Start a checklist on a record'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    template_id = fields.Many2one(
        'faizy.checklist.template', required=True,
        domain="[('res_model', '=', res_model), ('state', '=', 'released')]")
    sop_preview = fields.Text(related='template_id.description')

    def action_start(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        record.check_access('read')
        ck = self.env['faizy.checklist']._start(self.template_id, record=record, owner=self.env.user)
        return {'type': 'ir.actions.act_window', 'res_model': 'faizy.checklist',
                'res_id': ck.id, 'view_mode': 'form'}
