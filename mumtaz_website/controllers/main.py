from odoo import http
from odoo.http import request


class MumtazWebsite(http.Controller):

    @http.route('/', type='http', auth='public', website=True, sitemap=True)
    def home(self, **kwargs):
        return request.render('mumtaz_website.home')

    @http.route('/features', type='http', auth='public', website=True, sitemap=True)
    def features(self, **kwargs):
        return request.render('mumtaz_website.features')

    @http.route('/pricing', type='http', auth='public', website=True, sitemap=True)
    def pricing(self, **kwargs):
        # Load published plans if available
        plans = []
        try:
            plans = request.env['mumtaz.plan'].sudo().search(
                [('active', '=', True)], order='monthly_price asc'
            )
        except Exception:
            pass
        return request.render('mumtaz_website.pricing', {'plans': plans})

    @http.route('/contact', type='http', auth='public', website=True, sitemap=True)
    def contact(self, **kwargs):
        return request.render('mumtaz_website.contact')
