from odoo import fields, models


class VipAccessLog(models.Model):
    """Who looked at a Private or Royal client, and how. A form view logs
    one line per client; a list, search or export logs one line per query
    with the clients it returned, so a 200-row list costs one row here, not
    two hundred (gap-analysis finding 1, decided: log queries, not rows)."""
    _name = 'jewellery.vip.access.log'
    _description = 'Private / Royal client record access log'
    _order = 'date desc, id desc'

    partner_id = fields.Many2one('res.partner', ondelete='cascade', index=True,
                                 help='The client, for a form view; empty for a list or export, see the clients field.')
    partner_ids = fields.Many2many('res.partner', 'jewellery_vip_access_log_partner_rel', 'log_id', 'partner_id',
                                   string='Clients', help='Restricted clients a list, search or export returned.')
    user_id = fields.Many2one('res.users', required=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    action = fields.Selection([('view', 'Viewed'), ('list', 'Listed / searched'), ('export', 'Exported')],
                              default='view', required=True)
    count = fields.Integer(help='How many restricted clients the query returned.')
    note = fields.Char()
