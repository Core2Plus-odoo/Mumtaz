from odoo import http
from odoo.http import request


class MumtazWebsite(http.Controller):

    @http.route('/mumtaz', type='http', auth='public', website=True, sitemap=True)
    def home(self, **kwargs):
        return request.render('mumtaz_website.home')

    @http.route('/mumtaz/features', type='http', auth='public', website=True, sitemap=True)
    def features(self, **kwargs):
        return request.render('mumtaz_website.features')

    @http.route('/mumtaz/pricing', type='http', auth='public', website=True, sitemap=True)
    def pricing(self, **kwargs):
        plans = []
        try:
            plans = request.env['mumtaz.plan'].sudo().search(
                [('active', '=', True)], order='monthly_price asc'
            )
        except Exception:
            pass
        return request.render('mumtaz_website.pricing', {'plans': plans})

    @http.route('/mumtaz/contact', type='http', auth='public', website=True, sitemap=True)
    def contact(self, **kwargs):
        return request.render('mumtaz_website.contact')
