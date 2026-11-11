from odoo import fields, models


class ApiAudit(models.Model):
    """One row per API call.

    The front end and, later, the agents all come through the same door, so
    this is the record of who asked for what. It is written on a cursor of its
    own so that a call which fails -- and therefore rolls back -- still leaves
    its trace; an audit that vanishes with the error it should explain is no
    audit.
    """

    _name = 'jewellery.api.audit'
    _description = 'Jawhar API audit'
    _order = 'id desc'
    _log_access = False   # we store the actor and time ourselves; cheaper

    at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    user_id = fields.Many2one('res.users', index=True, ondelete='set null')
    login = fields.Char(help='Login attempted, for failed sign-ins with no user.')
    method = fields.Char(required=True)
    path = fields.Char(required=True, index=True)
    status = fields.Integer(required=True, help='HTTP status returned.')
    duration_ms = fields.Integer()
    remote_addr = fields.Char()
    error = fields.Char(help='Short error class, never a traceback or payload.')
