from odoo import fields, models

PAKISTAN_CITIES = [
    ('karachi', 'Karachi'), ('lahore', 'Lahore'), ('islamabad', 'Islamabad'),
    ('rawalpindi', 'Rawalpindi'), ('faisalabad', 'Faisalabad'),
    ('multan', 'Multan'), ('peshawar', 'Peshawar'), ('quetta', 'Quetta'),
    ('hyderabad', 'Hyderabad'), ('sialkot', 'Sialkot'), ('other', 'Other'),
]
EXPAT_COUNTRIES = [
    ('ae', 'UAE'), ('sa', 'Saudi Arabia'), ('gb', 'United Kingdom'),
    ('us', 'United States'), ('ca', 'Canada'), ('au', 'Australia'),
    ('qa', 'Qatar'), ('kw', 'Kuwait'), ('om', 'Oman'), ('other', 'Other'),
]
FAIZY_SERVICES = [
    ('medicines', 'Medicines & Pharmacy'), ('bills', 'Bills & Utilities'),
    ('grocery', 'Grocery & Daily'), ('eldercare', 'Eldercare Visits'),
    ('hospital', 'Hospital Escort'), ('nadra', 'NADRA / Documents'),
    ('passport', 'Passport Services'), ('eid', 'Eid / Occasions'),
    ('qurbani', 'Qurbani'), ('property', 'Property Visits'),
    ('court', 'Court & Legal'), ('multiple', 'Multiple Services'),
]
LEAD_SOURCES = [
    ('facebook', 'Facebook'), ('whatsapp', 'WhatsApp / Referral'),
    ('website', 'myfaizy.com'), ('instagram', 'Instagram'),
    ('embassy', 'Embassy Programme'), ('walk_in', 'Walk-in / Phone'),
    ('other', 'Other'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    faizy_family_city = fields.Selection(
        PAKISTAN_CITIES, string='Family city (Pakistan)')
    faizy_expat_country = fields.Selection(
        EXPAT_COUNTRIES, string='Expat country')
    faizy_service_interest = fields.Selection(
        FAIZY_SERVICES, string='Service interested in')
    faizy_lead_source = fields.Selection(
        LEAD_SOURCES, string='How they found us')
    faizy_family_size = fields.Integer(
        string='Family members to enrol', default=1)
    faizy_plan_interest = fields.Selection([
        ('lite', 'Lite — AED 26.50'),
        ('standard', 'Standard — AED 66.20'),
        ('family_pro', 'Family Pro — AED 119.20'),
        ('undecided', 'Undecided'),
    ], string='Plan interest', default='undecided')
    faizy_whatsapp_notes = fields.Text(
        string='WhatsApp conversation notes')
