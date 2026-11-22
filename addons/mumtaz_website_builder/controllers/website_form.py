"""Server-side validation for the Mumtaz demo form.

Odoo's native website form enforces only the fields the model itself marks
required; everything else is checked in the browser. A bot that posts
straight to /website/form/crm.lead would therefore create a lead with no
contact, no e-mail and no consent. This narrows the standard handler for our
one form (recognised by its fixed subject) and refuses such posts with the
message the form shows under the button. Every other website form on the
database behaves exactly as before.
"""
import re

from odoo import _
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.website.controllers.form import WebsiteForm

SUBJECT = 'Mumtaz Digital — Website demo request'
SOLUTION_TAGS = {
    'Mumtaz ERP': 'mumtaz_website_builder.tag_mumtaz_erp',
    'Industry solution': 'mumtaz_website_builder.tag_industry',
    'White-label ERP': 'mumtaz_website_builder.tag_white_label',
    'ZAKI AI': 'mumtaz_website_builder.tag_zaki',
}
_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')


class MumtazWebsiteForm(WebsiteForm):

    def _handle_website_form(self, model_name, **kwargs):
        if model_name == 'crm.lead' and kwargs.get('name') == SUBJECT:
            self._check_mumtaz_demo_request(kwargs)
            # the page markup stays literal (no QWeb inside the editable wrap), so the
            # solution arrives as text; the tag it maps to is set here
            tag = request.env.ref(SOLUTION_TAGS[kwargs['Interested solution']], raise_if_not_found=False)
            if tag:
                kwargs['tag_ids'] = str(tag.id)
        return super()._handle_website_form(model_name, **kwargs)

    @staticmethod
    def _check_mumtaz_demo_request(values):
        missing = []
        if len((values.get('contact_name') or '').strip()) < 2:
            missing.append(_('your name'))
        if not _EMAIL.match((values.get('email_from') or '').strip()):
            missing.append(_('a valid work e-mail'))
        if len((values.get('partner_name') or '').strip()) < 2:
            missing.append(_('the business name'))
        if values.get('Interested solution') not in SOLUTION_TAGS:
            missing.append(_('the solution you are interested in'))
        if not values.get('Privacy consent'):
            missing.append(_('your consent to be contacted'))
        if missing:
            raise ValidationError(_('Please provide %s.') % ', '.join(missing))
        phone = re.sub(r'\D', '', values.get('phone') or '')
        if values.get('phone') and len(phone) < 7:
            raise ValidationError(_('That phone number looks too short.'))
        # the honeypot the page renders off-screen: a filled value means a bot
        if (values.get('website_url_hp') or '').strip():
            raise ValidationError(_('Your request could not be sent.'))
        if request.httprequest.content_length and request.httprequest.content_length > 64 * 1024:
            raise ValidationError(_('The message is too long.'))
