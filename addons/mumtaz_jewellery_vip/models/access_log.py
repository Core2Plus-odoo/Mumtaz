from odoo import fields, models


class VipAccessLog(models.Model):
    _name = 'jewellery.vip.access.log'
    _description = 'Private / Royal client record access log'
    _order = 'date desc, id desc'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', required=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    action = fields.Selection([('view', 'Viewed')], default='view', required=True)
