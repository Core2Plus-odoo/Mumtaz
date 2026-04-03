from odoo import models, fields

class MumtazSmeProfile(models.Model):
    _name = 'mumtaz.sme.profile'
    _description = 'SME Profile'

    tenant_id = fields.Many2one('mumtaz.tenant', string='Tenant')