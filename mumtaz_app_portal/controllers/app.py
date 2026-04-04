import logging
from datetime import date, datetime, timedelta

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MumtazApp(http.Controller):
    """
    Unified Mumtaz customer app portal.

    URL scheme:
        /app                → home dashboard
        /app/erp            → ERP section (CRM, leads, campaigns)
        /app/zaki           → ZAKI AI section (CFO, transactions, AI)
        /app/marketplace    → Marketplace section (listings, inquiries)
        /app/account        → Account & plan section

    All routes are entitlement-gated: sections not included in the tenant's
    plan are still accessible but shown with upgrade prompts.
    """

    # ------------------------------------------------------------------ #
    # Auth helpers
    # ------------------------------------------------------------------ #

    def _require_app_user(self):
        """Return None if OK, or a redirect if the user should not be here."""
        user = request.env.user
        if not user or user._is_public():
            return request.redirect('/web/login?redirect=/app')
        # Admin-only users should be in the admin portal, not the app
        portal_type = user._detect_portal_type(user)
        if portal_type == 'admin':
            return request.redirect('/mumtaz/portal/admin')
        return None

    # ------------------------------------------------------------------ #
    # Shared context builder
    # ------------------------------------------------------------------ #

    def _base_ctx(self, active_section, section_title):
        """Build the context dict shared by all section templates."""
        env = request.env
        user = env.user
        company = env.company
        company_id = company.id
        today_date = date.today().strftime('%B %d, %Y')

        # Tenant profile
        tenant_profile = None
        try:
            tenant_profile = env['mumtaz.sme.profile'].sudo().search(
                [('company_id', '=', company_id)], limit=1
            )
        except Exception:
            pass

        # Active subscription
        subscription = None
        try:
            subscription = env['mumtaz.subscription'].sudo().search(
                [('company_id', '=', company_id), ('status', '!=', 'cancelled')],
                order='create_date desc',
                limit=1,
            )
        except Exception:
            pass

        # Feature entitlement — check which sections are accessible
        has_erp = _has_any_group(user, [
            'mumtaz_core.group_mumtaz_super_admin',
            'mumtaz_core.group_mumtaz_sme_admin',
            'mumtaz_core.group_mumtaz_analyst',
        ])
        has_zaki = _has_any_group(user, [
            'mumtaz_cfo_base.group_mumtaz_cfo_manager',
            'mumtaz_cfo_base.group_mumtaz_cfo_user',
        ])
        has_marketplace = _has_any_group(user, [
            'mumtaz_marketplace.group_mumtaz_marketplace_manager',
            'mumtaz_marketplace.group_mumtaz_marketplace_user',
        ])
        # Super admins always have everything
        if user.has_group('mumtaz_core.group_mumtaz_super_admin'):
            has_erp = has_zaki = has_marketplace = True

        # Alert counts for sidebar badges
        erp_alert_count = 0
        zaki_alert_count = 0
        marketplace_alert_count = 0

        return {
            'user': user,
            'company': company,
            'tenant_profile': tenant_profile,
            'subscription': subscription,
            'active_section': active_section,
            'section_title': section_title,
            'today_date': today_date,
            'has_erp': has_erp,
            'has_zaki': has_zaki,
            'has_marketplace': has_marketplace,
            'erp_alert_count': erp_alert_count,
            'zaki_alert_count': zaki_alert_count,
            'marketplace_alert_count': marketplace_alert_count,
            'zaki_workspace': None,
        }

    # ------------------------------------------------------------------ #
    # /app — Home dashboard
    # ------------------------------------------------------------------ #

    @http.route('/app', type='http', auth='user', website=True, sitemap=False)
    def app_home(self, **kwargs):
        guard = self._require_app_user()
        if guard:
            return guard

        env = request.env
        company_id = env.company.id
        ctx = self._base_ctx('home', 'Home')

        # ERP quick stats
        erp_leads_total = erp_opps_open = erp_opps_won = erp_campaign_count = 0
        if ctx['has_erp']:
            try:
                Lead = env['crm.lead'].sudo()
                erp_leads_total = Lead.search_count([('type', '=', 'lead')])
                erp_opps_open = Lead.search_count([('type', '=', 'opportunity'), ('probability', '<', 100)])
                erp_opps_won = Lead.search_count([('type', '=', 'opportunity'), ('stage_id.is_won', '=', True)])
                erp_campaign_count = env['lead.nurture.campaign'].sudo().search_count([('active', '=', True)])
            except Exception:
                pass

        # ZAKI quick stats
        zaki_tx_count = zaki_review_count = zaki_ai_sessions = 0
        zaki_net = zaki_workspace_obj = None
        if ctx['has_zaki']:
            try:
                ws = env['mumtaz.cfo.workspace'].sudo().search(
                    [('company_id', '=', company_id)], limit=1
                )
                zaki_workspace_obj = ws
                ctx['zaki_workspace'] = ws
                if ws:
                    Tx = env['mumtaz.cfo.transaction'].sudo()
                    zaki_tx_count = Tx.search_count([('workspace_id', '=', ws.id)])
                    zaki_review_count = Tx.search_count([
                        ('workspace_id', '=', ws.id),
                        ('requires_review', '=', True),
                    ])
                    income = sum(t.amount for t in Tx.search([
                        ('workspace_id', '=', ws.id), ('direction', '=', 'inflow')
                    ]))
                    expense = sum(t.amount for t in Tx.search([
                        ('workspace_id', '=', ws.id), ('direction', '=', 'outflow')
                    ]))
                    zaki_net = income - expense
                    zaki_ai_sessions = env['mumtaz.ai.session'].sudo().search_count(
                        [('company_id', '=', company_id)]
                    )
            except Exception:
                pass
            ctx['zaki_alert_count'] = zaki_review_count

        # Marketplace quick stats
        mp_total_listings = mp_my_listings = mp_new_inquiries = 0
        if ctx['has_marketplace']:
            try:
                Listing = env['mumtaz.marketplace.listing'].sudo()
                mp_total_listings = Listing.search_count([('state', '=', 'published')])
                mp_my_listings = Listing.search_count([
                    ('company_id', '=', company_id), ('state', '=', 'published')
                ])
                mp_new_inquiries = env['mumtaz.marketplace.inquiry'].sudo().search_count([
                    ('listing_id.company_id', '=', company_id), ('state', '=', 'new')
                ])
            except Exception:
                pass
            ctx['marketplace_alert_count'] = mp_new_inquiries

        profile_completeness = 0
        try:
            if ctx['tenant_profile']:
                profile_completeness = ctx['tenant_profile'].profile_completeness or 0
        except Exception:
            pass

        ctx.update({
            'erp_leads_total': erp_leads_total,
            'erp_opps_open': erp_opps_open,
            'erp_opps_won': erp_opps_won,
            'erp_campaign_count': erp_campaign_count,
            'zaki_tx_count': zaki_tx_count,
            'zaki_review_count': zaki_review_count,
            'zaki_net': zaki_net,
            'zaki_ai_sessions': zaki_ai_sessions,
            'mp_total_listings': mp_total_listings,
            'mp_my_listings': mp_my_listings,
            'mp_new_inquiries': mp_new_inquiries,
            'profile_completeness': profile_completeness,
        })
        return request.render('mumtaz_app_portal.app_home', ctx)

    # ------------------------------------------------------------------ #
    # /app/erp — ERP section
    # ------------------------------------------------------------------ #

    @http.route('/app/erp', type='http', auth='user', website=True, sitemap=False)
    def app_erp(self, **kwargs):
        guard = self._require_app_user()
        if guard:
            return guard

        env = request.env
        ctx = self._base_ctx('erp', 'ERP')

        leads_total = opps_open = opps_won = campaign_count = 0
        recent_leads = []
        scraper_source_count = scraper_job_count = total_scraped_records = 0
        last_scraper_job = None
        active_campaigns = []
        nurturing_leads = qualified_leads = converted_leads = 0
        recent_nurture_logs = []

        try:
            Lead = env['crm.lead'].sudo()
            leads_total = Lead.search_count([('type', '=', 'lead')])
            opps_open = Lead.search_count([('type', '=', 'opportunity'), ('probability', '<', 100)])
            opps_won = Lead.search_count([('type', '=', 'opportunity'), ('stage_id.is_won', '=', True)])
            recent_leads = Lead.search([('type', '=', 'lead')], order='create_date desc', limit=8)
        except Exception:
            pass

        try:
            ScraperJob = env['lead.scraper.job'].sudo()
            scraper_source_count = env['lead.scraper.source'].sudo().search_count([('active', '=', True)])
            scraper_job_count = ScraperJob.search_count([])
            total_scraped_records = env['lead.scraper.record'].sudo().search_count([])
            last_scraper_job = ScraperJob.search([], order='create_date desc', limit=1)
        except Exception:
            pass

        try:
            Campaign = env['lead.nurture.campaign'].sudo()
            campaign_count = Campaign.search_count([])
            active_campaigns = Campaign.search([('active', '=', True)], order='create_date desc', limit=5)
            NLead = env['crm.lead'].sudo()
            nurturing_leads = NLead.search_count([('nurture_stage', '=', 'nurturing')])
            qualified_leads = NLead.search_count([('nurture_stage', '=', 'qualified')])
            converted_leads = NLead.search_count([('nurture_stage', '=', 'converted')])
            recent_nurture_logs = env['lead.nurture.log'].sudo().search(
                [], order='timestamp desc', limit=5
            )
        except Exception:
            pass

        ctx['erp_alert_count'] = 0
        ctx.update({
            'leads_total': leads_total,
            'opps_open': opps_open,
            'opps_won': opps_won,
            'campaign_count': campaign_count,
            'recent_leads': recent_leads,
            'scraper_source_count': scraper_source_count,
            'scraper_job_count': scraper_job_count,
            'total_scraped_records': total_scraped_records,
            'last_scraper_job': last_scraper_job,
            'active_campaigns': active_campaigns,
            'nurturing_leads': nurturing_leads,
            'qualified_leads': qualified_leads,
            'converted_leads': converted_leads,
            'recent_nurture_logs': recent_nurture_logs,
        })
        return request.render('mumtaz_app_portal.app_erp', ctx)

    # ------------------------------------------------------------------ #
    # /app/zaki — ZAKI AI section
    # ------------------------------------------------------------------ #

    @http.route('/app/zaki', type='http', auth='user', website=True, sitemap=False)
    def app_zaki(self, **kwargs):
        guard = self._require_app_user()
        if guard:
            return guard

        env = request.env
        company_id = env.company.id
        ctx = self._base_ctx('zaki', 'ZAKI AI')

        workspace = None
        tx_count = review_count = 0
        income_total = expense_total = 0.0
        recent_txs = []
        ai_session_count = 0
        recent_sessions = []

        try:
            workspace = env['mumtaz.cfo.workspace'].sudo().search(
                [('company_id', '=', company_id)], limit=1
            )
            if workspace:
                Tx = env['mumtaz.cfo.transaction'].sudo()
                tx_count = Tx.search_count([('workspace_id', '=', workspace.id)])
                review_count = Tx.search_count([
                    ('workspace_id', '=', workspace.id),
                    ('requires_review', '=', True),
                ])
                inflows = Tx.search([('workspace_id', '=', workspace.id), ('direction', '=', 'inflow')])
                outflows = Tx.search([('workspace_id', '=', workspace.id), ('direction', '=', 'outflow')])
                income_total = sum(t.amount for t in inflows)
                expense_total = sum(t.amount for t in outflows)
                recent_txs = Tx.search(
                    [('workspace_id', '=', workspace.id)],
                    order='date desc',
                    limit=8,
                )
        except Exception:
            pass

        try:
            ai_session_count = env['mumtaz.ai.session'].sudo().search_count(
                [('company_id', '=', company_id)]
            )
            recent_sessions = env['mumtaz.ai.session'].sudo().search(
                [('company_id', '=', company_id)],
                order='create_date desc',
                limit=5,
            )
        except Exception:
            pass

        ctx['zaki_alert_count'] = review_count
        ctx['zaki_workspace'] = workspace
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
        return request.render('mumtaz_app_portal.app_zaki', ctx)

    # ------------------------------------------------------------------ #
    # /app/marketplace — Marketplace section
    # ------------------------------------------------------------------ #

    @http.route('/app/marketplace', type='http', auth='user', website=True, sitemap=False)
    def app_marketplace(self, **kwargs):
        guard = self._require_app_user()
        if guard:
            return guard

        env = request.env
        company_id = env.company.id
        ctx = self._base_ctx('marketplace', 'Marketplace')

        total_listings = my_listings = my_draft_listings = 0
        featured_listings = []
        inquiry_count = new_inquiry_count = 0
        recent_inquiries = []
        categories = []
        product_count = service_count = partnership_count = 0

        try:
            Listing = env['mumtaz.marketplace.listing'].sudo()
            total_listings = Listing.search_count([('state', '=', 'published')])
            my_listings = Listing.search_count([('company_id', '=', company_id), ('state', '=', 'published')])
            my_draft_listings = Listing.search_count([('company_id', '=', company_id), ('state', '=', 'draft')])
            featured_listings = Listing.search([('state', '=', 'published')], order='create_date desc', limit=6)
            product_count = Listing.search_count([('state', '=', 'published'), ('listing_type', '=', 'product')])
            service_count = Listing.search_count([('state', '=', 'published'), ('listing_type', '=', 'service')])
            partnership_count = Listing.search_count([('state', '=', 'published'), ('listing_type', '=', 'partnership')])
        except Exception:
            pass

        try:
            Inquiry = env['mumtaz.marketplace.inquiry'].sudo()
            inquiry_count = Inquiry.search_count([('listing_id.company_id', '=', company_id)])
            new_inquiry_count = Inquiry.search_count([
                ('listing_id.company_id', '=', company_id), ('state', '=', 'new')
            ])
            recent_inquiries = Inquiry.search(
                [('listing_id.company_id', '=', company_id)],
                order='create_date desc',
                limit=5,
            )
        except Exception:
            pass

        try:
            categories = env['mumtaz.marketplace.category'].sudo().search(
                [('active', '=', True)], order='sequence'
            )
        except Exception:
            pass

        ctx['marketplace_alert_count'] = new_inquiry_count
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
        return request.render('mumtaz_app_portal.app_marketplace', ctx)

    # ------------------------------------------------------------------ #
    # /app/account — Account & plan
    # ------------------------------------------------------------------ #

    @http.route('/app/account', type='http', auth='user', website=True, sitemap=False)
    def app_account(self, **kwargs):
        guard = self._require_app_user()
        if guard:
            return guard

        env = request.env
        company_id = env.company.id
        ctx = self._base_ctx('account', 'Account & Plan')

        # Features
        active_features = []
        locked_features = []
        try:
            all_features = env['mumtaz.feature'].sudo().search([('active', '=', True)])
            sub = ctx.get('subscription')
            if sub and sub.plan_id:
                plan_feat_ids = sub.plan_id.feature_ids.ids if hasattr(sub.plan_id, 'feature_ids') else []
                for f in all_features:
                    if f.id in plan_feat_ids:
                        active_features.append(f)
                    else:
                        locked_features.append(f)
            else:
                locked_features = list(all_features)
        except Exception:
            pass

        ctx.update({
            'active_features': active_features,
            'locked_features': locked_features,
        })
        return request.render('mumtaz_app_portal.app_account', ctx)


# ------------------------------------------------------------------ #
# Utility
# ------------------------------------------------------------------ #

def _has_any_group(user, group_xml_ids):
    """Return True if user has any of the given XML ID groups."""
    for xml_id in group_xml_ids:
        try:
            if user.has_group(xml_id):
                return True
        except Exception:
            pass
    return False
