import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subdomain → company middleware
# ---------------------------------------------------------------------------

class MumtazSlugMiddleware:
    """WSGI middleware that reads X-Mumtaz-Slug (set by nginx) and stores it
    on the WSGI environ so downstream Odoo code can pick up the org context.

    nginx sets:  proxy_set_header X-Mumtaz-Slug $slug;
    This middleware surfaces it as environ['mumtaz.slug'] and also sets
    HTTP_X_MUMTAZ_SLUG in the standard WSGI form so it's readable anywhere.
    """

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        slug = (
            environ.get("HTTP_X_MUMTAZ_SLUG", "").strip().lower() or
            _slug_from_host(environ.get("HTTP_HOST", ""))
        )
        if slug:
            environ["mumtaz.slug"] = slug
        return self.application(environ, start_response)


def _slug_from_host(host: str) -> str:
    """Extract the first hostname component if it looks like a Mumtaz tenant.

    'acme.mumtaz.digital' → 'acme'
    'mumtaz.digital'      → ''   (marketing site)
    'admin.mumtaz.digital'→ 'admin'
    """
    if not host:
        return ""
    hostname = host.split(":")[0]  # strip port
    parts = hostname.split(".")
    if len(parts) >= 3 and parts[-2] == "mumtaz" and parts[-1] == "digital":
        return parts[0]
    return ""


def get_current_slug() -> str:
    """Return the slug for the current HTTP request, or empty string."""
    try:
        return (request.httprequest.environ.get("mumtaz.slug") or "").strip()
    except RuntimeError:
        return ""

# ---------------------------------------------------------------------------
# Login redirect override
# ---------------------------------------------------------------------------
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
                    'Portal routing: uid=%s → %s (%s)',
                    uid, portal_url, user.mumtaz_portal_type,
                )
                return portal_url
        except Exception:
            _logger.exception('Portal routing: error detecting portal for uid=%s', uid)

        return super()._login_redirect(uid, redirect=redirect)


# ---------------------------------------------------------------------------
# Portal page controllers
# ---------------------------------------------------------------------------

class MumtazPortalRouting(http.Controller):
    """Serves landing pages for each Mumtaz portal."""

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

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

    def _resolve_slug_company(self):
        """Return the res.company matching the current request slug, or None.

        Looks up mumtaz.tenant by subdomain field, then falls back to
        res.company.name / res.company.website substring match.
        """
        slug = get_current_slug()
        if not slug:
            return None
        env = request.env.sudo()
        tenant = env["mumtaz.tenant"].search([("subdomain", "=", slug)], limit=1)
        if tenant and tenant.company_id:
            return tenant.company_id
        company = env["res.company"].search([("name", "ilike", slug)], limit=1)
        return company or None

    # ── Slug → company JSON endpoint ─────────────────────────────────── #

    @http.route(
        "/mumtaz/api/org",
        type="json",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_org_info(self):
        """Return org info for the current subdomain — used by the frontend
        to show the correct brand/logo before login."""
        slug = get_current_slug()
        if not slug:
            return {"slug": None, "company": None}
        company = self._resolve_slug_company()
        if not company:
            return {"slug": slug, "company": None}
        return {
            "slug": slug,
            "company": {
                "id":   company.id,
                "name": company.name,
                "logo": f"/web/image/res.company/{company.id}/logo" if company.logo else None,
            },
        }

    # ------------------------------------------------------------------ #
    # Generic portal router — /mumtaz/portal/home
    # ------------------------------------------------------------------ #

    @http.route(
        '/mumtaz/portal/home',
        type='http',
        auth='user',
        website=True,
        sitemap=False,
    )
    def portal_home(self, **kwargs):
        user = request.env.user
        url = user.get_mumtaz_portal_redirect_url()
        return request.redirect(url)

    # ------------------------------------------------------------------ #
    # Admin Control Plane portal
    # ------------------------------------------------------------------ #

    @http.route(
        '/mumtaz/portal/admin',
        type='http',
        auth='user',
        website=True,
        sitemap=False,
    )
    def portal_admin(self, **kwargs):
        guard = self._require_portal('admin')
        if guard:
            return guard

        env = request.env
        Tenant = env['mumtaz.tenant'].sudo()

        tenants_total = Tenant.search_count([])
        tenants_active = Tenant.search_count([('state', '=', 'active')])
        tenants_prov = Tenant.search_count([('state', '=', 'provisioning')])
        tenants_susp = Tenant.search_count([('state', '=', 'suspended')])
        tenants_draft = Tenant.search_count([('state', '=', 'draft')])
        tenants_archived = Tenant.search_count([('state', '=', 'archived')])
        recent_tenants = Tenant.search([], order='create_date desc', limit=10)

        ModuleBundle = env['mumtaz.module.bundle'].sudo()
        bundle_count = ModuleBundle.search_count([])
        bundles = ModuleBundle.search([], order='name', limit=8)

        # SME profiles
        sme_count = 0
        recent_smes = []
        try:
            SmeProfile = env['mumtaz.sme.profile'].sudo()
            sme_count = SmeProfile.search_count([])
            recent_smes = SmeProfile.search([], order='create_date desc', limit=5)
        except Exception:
            pass

        # Subscriptions
        subscription_count = 0
        active_subs = 0
        overdue_subs = 0
        try:
            Sub = env['mumtaz.subscription'].sudo()
            subscription_count = Sub.search_count([])
            active_subs = Sub.search_count([('status', '=', 'active')])
            overdue_subs = Sub.search_count([('status', '=', 'past_due')])
        except Exception:
            pass

        # Plans
        plan_count = 0
        try:
            plan_count = env['mumtaz.plan'].sudo().search_count([])
        except Exception:
            pass

        # Platform logs (last 24h errors)
        error_count = 0
        try:
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(hours=24)
            error_count = env['mumtaz.core.log'].sudo().search_count([
                ('level', '=', 'error'),
                ('create_date', '>=', cutoff.strftime('%Y-%m-%d %H:%M:%S')),
            ])
        except Exception:
            pass

        # Features & tenant features
        feature_count = 0
        try:
            feature_count = env['mumtaz.feature'].sudo().search_count([])
        except Exception:
            pass

        ctx = self._base_ctx('admin')
        ctx.update({
            'tenants_total': tenants_total,
            'tenants_active': tenants_active,
            'tenants_prov': tenants_prov,
            'tenants_susp': tenants_susp,
            'tenants_draft': tenants_draft,
            'tenants_archived': tenants_archived,
            'recent_tenants': recent_tenants,
            'bundle_count': bundle_count,
            'bundles': bundles,
            'sme_count': sme_count,
            'recent_smes': recent_smes,
            'subscription_count': subscription_count,
            'active_subs': active_subs,
            'overdue_subs': overdue_subs,
            'plan_count': plan_count,
            'error_count': error_count,
            'feature_count': feature_count,
        })
        return request.render('mumtaz_portal_routing.portal_admin_home', ctx)

    # ------------------------------------------------------------------ #
    # ERP portal
    # ------------------------------------------------------------------ #

    @http.route(
        '/mumtaz/portal/erp',
        type='http',
        auth='user',
        website=True,
        sitemap=False,
    )
    def portal_erp(self, **kwargs):
        guard = self._require_portal('erp')
        if guard:
            return guard

        env = request.env

        # CRM data
        leads_total = 0
        opps_open = 0
        opps_won = 0
        recent_leads = []
        try:
            Lead = env['crm.lead'].sudo()
            leads_total = Lead.search_count([('type', '=', 'lead')])
            opps_open = Lead.search_count([('type', '=', 'opportunity'), ('probability', '<', 100)])
            opps_won = Lead.search_count([('type', '=', 'opportunity'), ('stage_id.is_won', '=', True)])
            recent_leads = Lead.search(
                [('type', '=', 'lead')],
                order='create_date desc',
                limit=8,
            )
        except Exception:
            pass

        # Lead scraper
        last_scraper_job = None
        scraper_source_count = 0
        scraper_job_count = 0
        total_scraped_records = 0
        try:
            ScraperJob = env['lead.scraper.job'].sudo()
            last_scraper_job = ScraperJob.search([], order='create_date desc', limit=1)
            scraper_job_count = ScraperJob.search_count([])
            scraper_source_count = env['lead.scraper.source'].sudo().search_count([('active', '=', True)])
            total_scraped_records = env['lead.scraper.record'].sudo().search_count([])
        except Exception:
            pass

        # Lead nurture campaigns
        campaign_count = 0
        active_campaigns = []
        nurturing_leads = 0
        qualified_leads = 0
        converted_leads = 0
        try:
            Campaign = env['lead.nurture.campaign'].sudo()
            campaign_count = Campaign.search_count([])
            active_campaigns = Campaign.search([('active', '=', True)], order='create_date desc', limit=5)
            NurtureLead = env['crm.lead'].sudo()
            nurturing_leads = NurtureLead.search_count([('nurture_stage', '=', 'nurturing')])
            qualified_leads = NurtureLead.search_count([('nurture_stage', '=', 'qualified')])
            converted_leads = NurtureLead.search_count([('nurture_stage', '=', 'converted')])
        except Exception:
            pass

        # Marketplace listings
        listing_count = 0
        try:
            listing_count = env['mumtaz.marketplace.listing'].sudo().search_count(
                [('state', '=', 'published')]
            )
        except Exception:
            pass

        # Nurture logs (recent activity)
        recent_nurture_logs = []
        try:
            recent_nurture_logs = env['lead.nurture.log'].sudo().search(
                [], order='timestamp desc', limit=5
            )
        except Exception:
            pass

        ctx = self._base_ctx('erp')
        ctx.update({
            'leads_total': leads_total,
            'opps_open': opps_open,
            'opps_won': opps_won,
            'recent_leads': recent_leads,
            'last_scraper_job': last_scraper_job,
            'scraper_source_count': scraper_source_count,
            'scraper_job_count': scraper_job_count,
            'total_scraped_records': total_scraped_records,
            'listing_count': listing_count,
            'campaign_count': campaign_count,
            'active_campaigns': active_campaigns,
            'nurturing_leads': nurturing_leads,
            'qualified_leads': qualified_leads,
            'converted_leads': converted_leads,
            'recent_nurture_logs': recent_nurture_logs,
        })
        return request.render('mumtaz_portal_routing.portal_erp_home', ctx)

    # ------------------------------------------------------------------ #
    # ZAKI AI portal
    # ------------------------------------------------------------------ #

    @http.route(
        '/mumtaz/portal/zaki',
        type='http',
        auth='user',
        website=True,
        sitemap=False,
    )
    def portal_zaki(self, **kwargs):
        guard = self._require_portal('zaki')
        if guard:
            return guard

        env = request.env
        company_id = env.company.id

        # CFO workspace
        Workspace = env['mumtaz.cfo.workspace'].sudo()
        workspace = Workspace.search(
            [('company_id', '=', company_id)], limit=1
        )

        # Transactions
        tx_count = 0
        review_count = 0
        income_total = 0.0
        expense_total = 0.0
        recent_txs = []
        if workspace:
            Tx = env['mumtaz.cfo.transaction'].sudo()
            tx_count = Tx.search_count([('workspace_id', '=', workspace.id)])
            review_count = Tx.search_count([
                ('workspace_id', '=', workspace.id),
                ('requires_review', '=', True),
                ('is_duplicate', '=', False),
            ])
            income_txs = Tx.search([('workspace_id', '=', workspace.id), ('direction', '=', 'inflow')])
            expense_txs = Tx.search([('workspace_id', '=', workspace.id), ('direction', '=', 'outflow')])
            income_total = sum(t.amount for t in income_txs)
            expense_total = sum(t.amount for t in expense_txs)
            recent_txs = Tx.search(
                [('workspace_id', '=', workspace.id)],
                order='date desc', limit=8
            )

        # AI sessions
        ai_session_count = 0
        recent_sessions = []
        try:
            Session = env['mumtaz.ai.session'].sudo()
            ai_session_count = Session.search_count([('company_id', '=', company_id)])
            recent_sessions = Session.search(
                [('company_id', '=', company_id)],
                order='create_date desc', limit=5,
            )
        except Exception:
            pass

        ctx = self._base_ctx('zaki')
        ctx.update({
            'workspace': workspace,
            'tx_count': tx_count,
            'review_count': review_count,
            'income_total': income_total,
            'expense_total': expense_total,
            'recent_txs': recent_txs,
            'ai_session_count': ai_session_count,
            'recent_sessions': recent_sessions,
        })
        return request.render('mumtaz_portal_routing.portal_zaki_home', ctx)

    # ------------------------------------------------------------------ #
    # Marketplace portal
    # ------------------------------------------------------------------ #

    @http.route(
        '/mumtaz/portal/marketplace',
        type='http',
        auth='user',
        website=True,
        sitemap=False,
    )
    def portal_marketplace(self, **kwargs):
        guard = self._require_portal('marketplace')
        if guard:
            return guard

        env = request.env
        company_id = env.company.id

        total_listings = 0
        my_listings = 0
        featured_listings = []
        inquiry_count = 0
        new_inquiry_count = 0
        categories = []
        product_count = 0
        service_count = 0
        partnership_count = 0
        my_draft_listings = 0
        recent_inquiries = []

        try:
            Listing = env['mumtaz.marketplace.listing'].sudo()
            total_listings = Listing.search_count([('state', '=', 'published')])
            my_listings = Listing.search_count([
                ('company_id', '=', company_id),
                ('state', '=', 'published'),
            ])
            my_draft_listings = Listing.search_count([
                ('company_id', '=', company_id),
                ('state', '=', 'draft'),
            ])
            featured_listings = Listing.search(
                [('state', '=', 'published')],
                order='create_date desc',
                limit=6,
            )
            product_count = Listing.search_count([
                ('state', '=', 'published'),
                ('listing_type', '=', 'product'),
            ])
            service_count = Listing.search_count([
                ('state', '=', 'published'),
                ('listing_type', '=', 'service'),
            ])
            partnership_count = Listing.search_count([
                ('state', '=', 'published'),
                ('listing_type', '=', 'partnership'),
            ])
        except Exception:
            pass

        try:
            Inquiry = env['mumtaz.marketplace.inquiry'].sudo()
            inquiry_count = Inquiry.search_count([('listing_id.company_id', '=', company_id)])
            new_inquiry_count = Inquiry.search_count([
                ('listing_id.company_id', '=', company_id),
                ('state', '=', 'new'),
            ])
            recent_inquiries = Inquiry.search(
                [('listing_id.company_id', '=', company_id)],
                order='create_date desc',
                limit=5,
            )
        except Exception:
            pass

        try:
            Category = env['mumtaz.marketplace.category'].sudo()
            categories = Category.search([('active', '=', True)], order='sequence')
        except Exception:
            pass

        ctx = self._base_ctx('marketplace')
        ctx.update({
            'total_listings': total_listings,
            'my_listings': my_listings,
            'my_draft_listings': my_draft_listings,
            'featured_listings': featured_listings,
            'inquiry_count': inquiry_count,
            'new_inquiry_count': new_inquiry_count,
            'recent_inquiries': recent_inquiries,
            'categories': categories,
            'product_count': product_count,
            'service_count': service_count,
            'partnership_count': partnership_count,
        })
        return request.render('mumtaz_portal_routing.portal_marketplace_home', ctx)

    # ------------------------------------------------------------------ #
    # Portal switcher (super admins only)
    # ------------------------------------------------------------------ #

    @http.route(
        '/mumtaz/portal/switch',
        type='http',
        auth='user',
        website=True,
        sitemap=False,
    )
    def portal_switch(self, **kwargs):
        user = request.env.user
        portals = user.get_accessible_portals()
        if len(portals) == 1:
            return request.redirect(portals[0]['url'])
        ctx = self._base_ctx('switch')
        ctx['portals'] = portals
        return request.render('mumtaz_portal_routing.portal_switcher', ctx)
