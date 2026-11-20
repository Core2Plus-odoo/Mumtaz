"""Compliance on the decision cards: the threshold waiting for finance to
confirm it, identity documents about to expire, screening matches open."""
from datetime import timedelta

from odoo import _, api, fields, models


class OwnerCard(models.Model):
    _inherit = 'jewellery.owner.card'

    kind = fields.Selection(selection_add=[('aml', 'AML and KYC')], ondelete={'aml': 'cascade'})

    @api.model
    def _desired(self):
        out = super()._desired()
        env = self.env
        cfg = env['jewellery.aml.event'].config()
        if not cfg['configured']:
            out.append(dict(kind='aml', res_model='', res_id=0, priority=9,
                            title=_('Confirm the AML cash threshold'),
                            detail=_('No cash threshold is in force: the counter sells as before and nothing is checked. '
                                     'The named finance manager sets the amount and the window on the Compliance screen; '
                                     'nothing here is validated law.'),
                            recommendation=_('Finance manager: confirm the threshold and the window'), impact=''))
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        for p in env['res.partner'].sudo().search([('kyc_status', '=', 'verified'), ('kyc_id_expiry', '!=', False),
                                                   ('kyc_id_expiry', '<=', soon)]):
            late = p.kyc_id_expiry < today
            out.append(dict(kind='aml', res_model='res.partner', res_id=p.id, priority=7 if late else 5,
                            restricted=p.jewellery_restricted,
                            title=_('%(n)s: identity document %(w)s', n=p.name, w=_('expired') if late else _('expires soon')),
                            detail=_('%(doc)s ending %(l4)s, expiry %(d)s.', doc=p.kyc_id_type or '', l4=p.kyc_id_last4 or '', d=p.kyc_id_expiry),
                            recommendation=_('Ask for a current document at her next visit'), impact=''))
        for p in env['res.partner'].sudo().search([('aml_screening_status', '=', 'match')]):
            out.append(dict(kind='aml', res_model='res.partner', res_id=p.id, priority=10, restricted=p.jewellery_restricted,
                            title=_('%s: screening match open') % p.name,
                            detail=_('Cash at or above the threshold is refused for her until a manager records a decision.'),
                            recommendation=_('Compliance decision: clear, or keep refusing'), impact=''))
        return out
