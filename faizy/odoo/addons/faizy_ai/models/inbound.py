from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .utils import G_COMMS, is_approver, normalize_phone


class FaizyAIInbound(models.Model):
    _name = 'faizy.ai.inbound'
    _description = 'Faizy inbound WhatsApp message'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    wa_id = fields.Char(string='WhatsApp message ID', index=True, readonly=True, copy=False)
    phone = fields.Char(readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer')
    order_id = fields.Many2one('faizy.order')
    body = fields.Text(readonly=True)
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    state = fields.Selection([('new', 'New'), ('handled', 'Handled'), ('ignored', 'Ignored')],
                             default='new', required=True, tracking=True, index=True)
    handled_by_id = fields.Many2one('res.users', readonly=True)

    _unique_wa_id = models.Constraint('UNIQUE(wa_id)', 'This WhatsApp message is already logged.')

    @api.depends('phone', 'body')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s: %s' % (rec.phone or '?', (rec.body or '')[:40])

    def action_handled(self):
        if not is_approver(self.env):
            raise UserError(_('Only Faizy staff can close an inbound message.'))
        self.write({'state': 'handled', 'handled_by_id': self.env.uid})

    def action_ignore(self):
        if not is_approver(self.env):
            raise UserError(_('Only Faizy staff can close an inbound message.'))
        self.write({'state': 'ignored', 'handled_by_id': self.env.uid})

    @api.model
    def _find_partner(self, digits):
        if len(digits) < 9:
            return self.env['res.partner']
        # Stored phones carry spaces, dashes and plus signs, so compare digits only.
        self.env.cr.execute("""
            SELECT id FROM res_partner
             WHERE active AND phone IS NOT NULL
               AND regexp_replace(phone, '\\D', '', 'g') LIKE %s
             ORDER BY id LIMIT 1
        """, ['%' + digits[-9:]])
        row = self.env.cr.fetchone()
        return self.env['res.partner'].sudo().browse(row[0]) if row else self.env['res.partner']

    @api.model
    def process_whatsapp_payload(self, payload):
        """Log inbound text messages from a Meta Cloud API webhook payload.

        Returns the created records. Runs with sudo: the webhook has no user.
        """
        created = self.sudo().browse()
        group = self.env.ref(G_COMMS, raise_if_not_found=False)
        notify = group.sudo().user_ids[:2] if group else self.env['res.users']
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                for msg in value.get('messages', []):
                    wa_id = msg.get('id')
                    if not wa_id or self.sudo().search_count([('wa_id', '=', wa_id)]):
                        continue
                    text = (msg.get('text') or {}).get('body') or '[%s message]' % msg.get('type')
                    digits = normalize_phone(msg.get('from'))
                    partner = self._find_partner(digits)
                    rec = self.sudo().create({
                        'wa_id': wa_id,
                        'phone': '+' + digits if digits else False,
                        'body': text,
                        'partner_id': partner.id,
                    })
                    summary = _('Reply needed: %s', partner.display_name or rec.phone)
                    for user in notify:
                        rec.activity_schedule('mail.mail_activity_data_todo',
                                              user_id=user.id, summary=summary)
                    created |= rec
        return created
