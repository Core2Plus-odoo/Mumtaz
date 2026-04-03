import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.web.controllers.home import Home as _WebHome
    _BASE_HOME = _WebHome
except ImportError:
    try:
        from odoo.addons.web.controllers.main import Home as _WebHome
        _BASE_HOME = _WebHome
    except ImportError:
        _BASE_HOME = http.Controller


class MumtazHome(_BASE_HOME):
    """Extends the Odoo login controller to route Mumtaz users to their portal."""

    def _login_redirect(self, uid, redirect=None):
        if redirect:
            return redirect

        try:
            user = request.env['res.users'].sudo().browse(uid)
            portal_url = user.get_mumtaz_portal_redirect_url()
            if portal_url and portal_url != '/web':
                _logger.info(
                    'Portal routing: uid=%s -> %s (%s)',
                    uid, portal_url, user.mumtaz_portal_type,
                )
                return portal_url
        except Exception:
            _logger.exception('Portal routing: error detecting portal for uid=%s', uid)

        return super()._login_redirect(uid, redirect=redirect)


class MumtazPortalRouting(http.Controller):
    """Serves landing pages for each Mumtaz portal."""

    def _require_portal(self, portal_type):
        user = request.env.user
        if not user or user._is_public():
            return request.redirect('/web/login?redirect=/mumtaz/portal/' + portal_type)

        detected = user._detect_portal_type(user)
        is_super = user.has_group('mumtaz_core.group_mumtaz_super_admin')

        if detected != portal_type and not is_super:
            correct_url = user.get_mumtaz_portal_redirect_url()
            return request.redirect(correct_url)

        return None

    def _base_ctx(self, portal_type):
        user = request.env.user
        return {
            'user': user,
            'portal_type': portal_type,
            'portal_label': user.get_mumtaz_portal_label(),
            'accessible_portals': user.get_accessible_portals(),
            'company': request.env.company,
        }

    @http.route('/mumtaz/portal/home', type='http', auth='user', website=True, sitemap=False)
    def portal_home(self, **kwargs):
        user = request.env.user
        url = user.get_mumtaz_portal_redirect_url()
        return request.redirect(url)

    @http.route('/mumtaz/portal/admin', type='http', auth='user', website=True, sitemap=False)
    def portal_admin(self, **kwargs):
        guard = self._require_portal('admin')
        if guard:
            return guard

        env = request.env
        Tenant = env['mumtaz.tenant'].sudo()

        tenants_total  = Tenant.search_count([])
        tenants_active = Tenant.search_count([('state', '=', 'active')])
        tenants_prov   = Tenant.search_count([('state', '=', 'provisioning')])
        tenants_susp   = Tenant.search_count([('state', '=', 'suspended')])
        recent_tenants = Tenant.search([], order='create_date desc', limit=10)

        ModuleBundle = env['mumtaz.module.bundle'].sudo()
        bundle_count = ModuleBundle.search_count([])

        ctx = self._base_ctx('admin')
        ctx.update({
            'tenants_total':  tenants_total,
            'tenants_active': tenants_active,
            'tenants_prov':   tenants_prov,
            'tenants_susp':   tenants_susp,
            'recent_tenants': recent_tenants,
            'bundle_count':   bundle_count,
        })
        return request.render('mumtaz_portal_routing.portal_admin_home', ctx)

    @http.route('/mumtaz/portal/erp', type='http', auth='user', website=True, sitemap=False)
    def portal_erp(self, **kwargs):
        guard = self._require_portal('erp')
        if guard:
            return guard

        env = request.env
        Lead = env['crm.lead'].sudo()

        leads_total = Lead.search_count([('type', '=', 'lead')])
        opps_open   = Lead.search_count([('type', '=', 'opportunity'), ('probability', '<', 100)])
        opps_won    = Lead.search_count([('type', '=', 'opportunity'), ('stage_id.is_won', '=', True)])
        recent_leads = Lead.search([('type', '=', 'lead')], order='create_date desc', limit=8)

        last_scraper_job = None
        try:
            ScraperJob = env['mumtaz.lead.scraper.job'].sudo()
            last_scraper_job = ScraperJob.search([], order='create_date desc', limit=1)
        except Exception:
            pass

        listing_count = 0
        try:
            listing_count = env['mumtaz.marketplace.listing'].sudo().search_count([('state', '=', 'published')])
        except Exception:
            pass

        ctx = self._base_ctx('erp')
        ctx.update({
            'leads_total':      leads_total,
            'opps_open':        opps_open,
            'opps_won':         opps_won,
            'recent_leads':     recent_leads,
            'last_scraper_job': last_scraper_job,
            'listing_count':    listing_count,
        })
        return request.render('mumtaz_portal_routing.portal_erp_home', ctx)

    @http.route('/mumtaz/portal/zaki', type='http', auth='user', website=True, sitemap=False)
    def portal_zaki(self, **kwargs):
        guard = self._require_portal('zaki')
        if guard:
            return guard

        env = request.env
        company_id = env.company.id

        Workspace = env['mumtaz.cfo.workspace'].sudo()
        workspace = Workspace.search([('company_id', '=', company_id)], limit=1)

        tx_count = 0
        review_count = 0
        income_total = 0.0
        expense_total = 0.0
        recent_txs = []
        if workspace:
            Tx = env['mumtaz.cfo.transaction'].sudo()
            tx_count = Tx.search_count([('batch_id.workspace_id', '=', workspace.id)])
            review_count = Tx.search_count([
                ('batch_id.workspace_id', '=', workspace.id),
                ('requires_review', '=', True),
                ('is_duplicate', '=', False),
            ])
            income_txs  = Tx.search([('batch_id.workspace_id', '=', workspace.id), ('direction', '=', 'inflow')])
            expense_txs = Tx.search([('batch_id.workspace_id', '=', workspace.id), ('direction', '=', 'outflow')])
            income_total  = sum(t.amount for t in income_txs)
            expense_total = sum(t.amount for t in expense_txs)
            recent_txs = Tx.search([('batch_id.workspace_id', '=', workspace.id)], order='date desc', limit=8)

        ai_session_count = 0
        recent_sessions  = []
        try:
            Session = env['mumtaz.ai.session'].sudo()
            ai_session_count = Session.search_count([('company_id', '=', company_id)])
            recent_sessions  = Session.search([('company_id', '=', company_id)], order='create_date desc', limit=5)
        except Exception:
            pass

        ctx = self._base_ctx('zaki')
        ctx.update({
            'workspace':         workspace,
            'tx_count':          tx_count,
            'review_count':      review_count,
            'income_total':      income_total,
            'expense_total':     expense_total,
            'recent_txs':        recent_txs,
            'ai_session_count':  ai_session_count,
            'recent_sessions':   recent_sessions,
        })
        return request.render('mumtaz_portal_routing.portal_zaki_home', ctx)

    @http.route('/mumtaz/portal/marketplace', type='http', auth='user', website=True, sitemap=False)
    def portal_marketplace(self, **kwargs):
        guard = self._require_portal('marketplace')
        if guard:
            return guard

        env = request.env
        company_id = env.company.id
        Listing = env['mumtaz.marketplace.listing'].sudo()

        total_listings   = Listing.search_count([('state', '=', 'published')])
        my_listings      = Listing.search_count([('company_id', '=', company_id)])
        featured_listings = Listing.search([('state', '=', 'published')], order='create_date desc', limit=6)

        inquiry_count = 0
        try:
            Inquiry = env['mumtaz.marketplace.inquiry'].sudo()
            inquiry_count = Inquiry.search_count([('listing_id.company_id', '=', company_id)])
        except Exception:
            pass

        ctx = self._base_ctx('marketplace')
        ctx.update({
            'total_listings':    total_listings,
            'my_listings':       my_listings,
            'featured_listings': featured_listings,
            'inquiry_count':     inquiry_count,
        })
        return request.render('mumtaz_portal_routing.portal_marketplace_home', ctx)

    @http.route('/mumtaz/portal/switch', type='http', auth='user', website=True, sitemap=False)
    def portal_switch(self, **kwargs):
        user = request.env.user
        portals = user.get_accessible_portals()
        if len(portals) == 1:
            return request.redirect(portals[0]['url'])
        ctx = self._base_ctx('switch')
        ctx['portals'] = portals
        return request.render('mumtaz_portal_routing.portal_switcher', ctx)
