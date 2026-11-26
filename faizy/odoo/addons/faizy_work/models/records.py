from odoo import api, models

from .checklist_mixin import AUTO_ORDERS_PARAM


class FaizyOrder(models.Model):
    _name = 'faizy.order'
    _inherit = ['faizy.order', 'faizy.checklist.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        if self.env['ir.config_parameter'].sudo().get_param(AUTO_ORDERS_PARAM) == 'on':
            ops = self.env['faizy.routing']._role_user('ops')
            for order in orders:
                order.sudo()._checklist_start('order_assignment_execution', owner=ops)
        return orders

    def action_assign(self):
        self._checklist_gate('assign', what=self.env._('assign the order'))
        return super().action_assign()

    def action_complete(self):
        # Runs before faizy_pilot's evidence gate (this module loads later), so a
        # refusal never reaches billing. The evidence gate itself is unchanged.
        self._checklist_gate('complete', what=self.env._('complete the order'))
        return super().action_complete()


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'faizy.checklist.mixin']


class FaizyAIDraft(models.Model):
    _name = 'faizy.ai.draft'
    _inherit = ['faizy.ai.draft', 'faizy.checklist.mixin']

    def action_approve(self):
        self._checklist_gate('approve', what=self.env._('approve the draft'))
        return super().action_approve()
