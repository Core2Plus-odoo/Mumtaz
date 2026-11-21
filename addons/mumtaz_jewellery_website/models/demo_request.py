"""A demo request from the public site: the only thing the site writes.

Validated, capped per contact and per day, consent stored with the record,
and a CRM lead so the follow-up lives where the sales team works. Nothing is
sent to the visitor by the system: a person calls or writes.
"""
import hashlib
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

STORES = [('1', '1 store'), ('2-5', '2 to 5 stores'), ('6-20', '6 to 20 stores'), ('20+', 'More than 20 stores')]
COUNTRIES = [('ae', 'United Arab Emirates'), ('sa', 'Saudi Arabia'), ('qa', 'Qatar'), ('kw', 'Kuwait'),
             ('bh', 'Bahrain'), ('om', 'Oman'), ('pk', 'Pakistan'), ('other', 'Other')]
STATES = [('new', 'New'), ('contacted', 'Contacted'), ('qualified', 'Qualified'), ('closed', 'Closed')]
CONSENT_TEXT = ('I agree that Mumtaz Digital contacts me about Jawhar using the details above, '
                'and keeps them for that purpose until I ask otherwise.')
_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')


def _clean_phone(value):
    value = (value or '').strip()
    keep = '+' if value.startswith('+') else ''
    return keep + re.sub(r'\D', '', value)


class DemoRequest(models.Model):
    _name = 'jewellery.demo.request'
    _description = 'Jawhar demo request'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(required=True, readonly=True, copy=False, default=lambda self: _('New'))
    company_name = fields.Char(required=True)
    contact_name = fields.Char(required=True)
    role = fields.Char()
    email = fields.Char(required=True)
    phone = fields.Char()
    country = fields.Selection(COUNTRIES, required=True, default='ae')
    stores = fields.Selection(STORES, required=True, default='1')
    message = fields.Text()
    lang = fields.Selection([('en', 'English'), ('ar', 'Arabic')], default='en', required=True)
    source_page = fields.Char(help='Path of the page the form was on.')
    consent_text = fields.Char(readonly=True, help='The sentence the visitor agreed to, verbatim.')
    consent_at = fields.Datetime(readonly=True)
    contact_hash = fields.Char(index=True, readonly=True,
                               help='Hash of the e-mail, for the daily cap. The address itself is on the record.')
    state = fields.Selection(STATES, default='new', required=True, tracking=True)
    lead_id = fields.Many2one('crm.lead', string='CRM lead', readonly=True, ondelete='set null')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('jewellery.demo.request') or _('New')
        return super().create(vals_list)

    # -- the public side ---------------------------------------------------
    @api.model
    def _cap(self):
        # sudo: system parameter; only administrators may read ir.config_parameter
        param = self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.demo_request_daily_cap')
        try:
            return max(1, int(param))
        except (TypeError, ValueError):
            return 3

    @api.model
    def create_public(self, company_name, contact_name, email, consent, phone=None, role=None, country='ae',
                      stores='1', message=None, lang='en', source_page=None):
        """What the website may do: one request, validated, capped, consented.
        Runs under sudo for the public user; returns a payload with no
        internal ids."""
        company_name = (company_name or '').strip()[:120]
        contact_name = (contact_name or '').strip()[:120]
        email = (email or '').strip().lower()[:120]
        phone = _clean_phone(phone)[:32]
        if len(company_name) < 2 or len(contact_name) < 2:
            raise UserError(_('Tell us the name of the business and who to ask for.'))
        if not _EMAIL.match(email):
            raise UserError(_('An e-mail address is needed so a person can write back.'))
        if phone and len(phone) < 7:
            raise UserError(_('That phone number looks short.'))
        if not consent:
            raise UserError(_('We can only call or write if you agree to be contacted.'))
        country = country if country in dict(COUNTRIES) else 'other'
        stores = stores if stores in dict(STORES) else '1'
        lang = 'ar' if (lang or '').startswith('ar') else 'en'
        digest = hashlib.sha256(email.encode()).hexdigest()
        since = fields.Datetime.now() - timedelta(days=1)
        # sudo: public website door: per-contact daily cap counted over all requests; no record is read back
        if self.sudo().search_count([('contact_hash', '=', digest), ('create_date', '>=', since)]) >= self._cap():
            raise UserError(_('We already have your request. A person will be in touch.'))
        tag = self.env.ref('mumtaz_jewellery_website.tag_jawhar_demo', raise_if_not_found=False)
        # sudo: public website door: the lead is created for the sales team after validation; the visitor gets only a reference
        lead = self.env['crm.lead'].sudo().create({
            'name': _('Jawhar demo · %(company)s', company=company_name),
            'type': 'lead',
            'partner_name': company_name, 'contact_name': contact_name, 'function': (role or '')[:120] or False,
            'email_from': email, 'phone': phone or False,
            'description': _('Demo request from the website (%(page)s).\nCountry: %(country)s. Stores: %(stores)s. '
                             'Language: %(lang)s.\n\n%(msg)s',
                             page=(source_page or '/')[:200], country=dict(COUNTRIES)[country],
                             stores=dict(STORES)[stores], lang=lang, msg=(message or '')[:2000] or '-'),
            'tag_ids': [(4, tag.id)] if tag else False,
        })
        # sudo: public website door: the request is created after validation and the cap; no internal id leaves
        rec = self.sudo().create({
            'company_name': company_name, 'contact_name': contact_name, 'role': (role or '')[:120] or False,
            'email': email, 'phone': phone or False, 'country': country, 'stores': stores,
            'message': (message or '')[:2000] or False, 'lang': lang,
            'source_page': (source_page or '')[:200] or False,
            'consent_text': CONSENT_TEXT, 'consent_at': fields.Datetime.now(), 'contact_hash': digest,
            'lead_id': lead.id,
        })
        return {'reference': rec.name}
