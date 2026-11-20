from datetime import timedelta

from odoo import api, fields, models, _

KINDS = [('birthday', 'Birthday'), ('anniversary', 'Anniversary'), ('wedding', 'Wedding'),
         ('eid', 'Eid'), ('diwali', 'Diwali'), ('national_day', 'National day'), ('other', 'Other')]


class Occasion(models.Model):
    _name = 'jewellery.occasion'
    _description = 'Client occasion'
    _order = 'date'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    kind = fields.Selection(KINDS, required=True, default='birthday')
    date = fields.Date(required=True)
    recurring = fields.Boolean(default=True, help='Repeats every year on the same day.')
    lead_days = fields.Integer(default=21, help='Prepare this many days before.')
    note = fields.Char()
    last_prepared = fields.Date(readonly=True)

    def _next_date(self, today):
        self.ensure_one()
        if not self.recurring:
            return self.date
        try:
            d = self.date.replace(year=today.year)
        except ValueError:  # 29 Feb
            d = self.date.replace(year=today.year, day=28)
        if d < today:
            try:
                d = self.date.replace(year=today.year + 1)
            except ValueError:
                d = self.date.replace(year=today.year + 1, day=28)
        return d

    def _draft_text(self):
        self.ensure_one()
        kind = dict(KINDS)[self.kind]
        return _('Draft for %(name)s (%(kind)s). Suggest a handwritten note and one or two pieces from the '
                 'client file. Nothing is sent automatically; the relationship manager sends it.',
                 name=self.partner_id.name, kind=kind)

    @api.model
    def _cron_prepare(self):
        today = fields.Date.context_today(self)
        for occ in self.sudo().search([]):
            nxt = occ._next_date(today)
            if nxt < today or (nxt - today).days > occ.lead_days:
                continue
            if occ.last_prepared and occ.last_prepared.year == nxt.year:
                continue
            p = occ.partner_id
            owner = p.relationship_manager_id or p.deputy_id or self.env.ref('base.user_admin')
            p.activity_schedule('mail.mail_activity_data_todo', date_deadline=nxt - timedelta(days=3),
                                summary=_('Prepare %s for %s') % (dict(KINDS)[occ.kind], p.name),
                                note=occ._draft_text(), user_id=owner.id)
            occ.last_prepared = today
