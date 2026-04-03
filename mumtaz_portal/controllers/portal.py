import base64
import json
import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _get_sme_profile():
    """Return the SME profile for the current user's company, or None."""
    try:
        return request.env['mumtaz.sme.profile'].search(
            [('company_id', '=', request.env.company.id)], limit=1
        )
    except Exception:
        return None


def _get_onboarding():
    """Return the onboarding checklist for the current company, or None."""
    try:
        return request.env['mumtaz.onboarding.checklist'].search(
            [('company_id', '=', request.env.company.id)], limit=1
        )
    except Exception:
        return None


def _get_cfo_workspace():
    """Return the primary CFO workspace for the current company, or None."""
    try:
        return request.env['mumtaz.cfo.workspace'].search(
            [('company_id', '=', request.env.company.id)], limit=1, order='id asc'
        )
    except Exception:
        return None


def _base_values(active_page='dashboard'):
    """Common template values shared by all portal pages."""
    profile = _get_sme_profile()
    onboarding = _get_onboarding()
    user = request.env.user
    return {
        'active_page': active_page,
        'user': user,
        'company': request.env.company,
        'sme_profile': profile,
        'onboarding': onboarding,
        'onboarding_pct': onboarding.progress if onboarding else 0,
        'onboarding_done': (onboarding.progress >= 100) if onboarding else False,
    }


class MumtazPortal(http.Controller):

    # ──────────────────────────────────────────────────────────────────
    # Root redirect
    # ──────────────────────────────────────────────────────────────────

    @http.route('/mumtaz', type='http', auth='user', website=True)
    def portal_root(self, **kw):
        return request.redirect('/mumtaz/dashboard')

    # ──────────────────────────────────────────────────────────────────
    # Dashboard
    # ──────────────────────────────────────────────────────────────────

    @http.route('/mumtaz/dashboard', type='http', auth='user', website=True)
    def portal_dashboard(self, **kw):
        values = _base_values('dashboard')

        # Recent AI session for the "last briefing" widget
        try:
            last_session = request.env['mumtaz.ai.session'].search(
                [('company_id', '=', request.env.company.id)],
                order='create_date desc', limit=1
            )
            values['last_ai_session'] = last_session
        except Exception:
            values['last_ai_session'] = None

        # CFO workspace KPIs
        workspace = _get_cfo_workspace()
        values['workspace'] = workspace
        if workspace:
            try:
                txn_model = request.env['mumtaz.cfo.transaction']
                values['txn_count'] = txn_model.search_count(
                    [('workspace_id', '=', workspace.id)]
                )
                values['review_count'] = request.env['mumtaz.cfo.review.item'].search_count(
                    [('transaction_id.workspace_id', '=', workspace.id),
                     ('status', '=', 'open')]
                )
                # Income / expense totals
                income = txn_model.search([
                    ('workspace_id', '=', workspace.id),
                    ('direction', '=', 'in'),
                ])
                expense = txn_model.search([
                    ('workspace_id', '=', workspace.id),
                    ('direction', '=', 'out'),
                ])
                values['total_income'] = sum(t.amount for t in income)
                values['total_expense'] = sum(t.amount for t in expense)
                values['net_position'] = values['total_income'] - values['total_expense']
            except Exception:
                values.update({'txn_count': 0, 'review_count': 0,
                                'total_income': 0, 'total_expense': 0, 'net_position': 0})
        else:
            values.update({'txn_count': 0, 'review_count': 0,
                            'total_income': 0, 'total_expense': 0, 'net_position': 0})

        return request.render('mumtaz_portal.portal_dashboard', values)

    # ──────────────────────────────────────────────────────────────────
    # AI Chat
    # ──────────────────────────────────────────────────────────────────

    @http.route('/mumtaz/ai', type='http', auth='user', website=True)
    def portal_ai(self, session_id=None, **kw):
        values = _base_values('ai')

        # Load or create session
        session = None
        if session_id:
            session = request.env['mumtaz.ai.session'].browse(int(session_id))
            if not session.exists() or session.company_id.id != request.env.company.id:
                session = None

        # Recent sessions for history list
        try:
            recent_sessions = request.env['mumtaz.ai.session'].search(
                [('company_id', '=', request.env.company.id)],
                order='create_date desc', limit=10
            )
        except Exception:
            recent_sessions = []

        values['ai_session'] = session
        values['recent_sessions'] = recent_sessions

        # Load messages for active session
        if session:
            try:
                values['ai_messages'] = request.env['mumtaz.ai.message'].search(
                    [('session_id', '=', session.id)],
                    order='create_date asc'
                )
            except Exception:
                values['ai_messages'] = []
        else:
            values['ai_messages'] = []

        return request.render('mumtaz_portal.portal_ai', values)

    @http.route('/mumtaz/ai/chat', type='json', auth='user', csrf=False)
    def portal_ai_chat(self, message, session_id=None, **kw):
        """Send a message to Mumtaz AI and return the response."""
        message = (message or '').strip()
        if not message:
            return {'error': 'Empty message'}
        try:
            session = None
            if session_id:
                session = request.env['mumtaz.ai.session'].browse(int(session_id))
                if not session.exists():
                    session = None

            if not session:
                session = request.env['mumtaz.ai.session'].create({
                    'name': f'Portal Chat – {request.env.user.name}',
                    'company_id': request.env.company.id,
                    'user_id': request.env.user.id,
                    'prompt': message,
                })
            else:
                session.prompt = message

            result = request.env['mumtaz.ai.service'].process_user_prompt(session, message)
            return {
                'session_id': session.id,
                'response': result.get('response', ''),
                'intent': result.get('intent', 'general'),
                'model_used': result.get('model_used', ''),
            }
        except Exception as exc:
            _logger.exception("Portal AI chat error: %s", exc)
            return {'error': str(exc)}

    @http.route('/mumtaz/ai/new', type='http', auth='user', website=True)
    def portal_ai_new(self, **kw):
        return request.redirect('/mumtaz/ai')

    # ──────────────────────────────────────────────────────────────────
    # CFO Workspace
    # ──────────────────────────────────────────────────────────────────

    @http.route('/mumtaz/cfo', type='http', auth='user', website=True)
    def portal_cfo(self, workspace_id=None, page=1, **kw):
        values = _base_values('cfo')
        page = int(page)

        # Select workspace
        try:
            workspaces = request.env['mumtaz.cfo.workspace'].search(
                [('company_id', '=', request.env.company.id)]
            )
            workspace = None
            if workspace_id:
                workspace = workspaces.filtered(lambda w: w.id == int(workspace_id))[:1]
            if not workspace:
                workspace = workspaces[:1]
            values['workspaces'] = workspaces
            values['workspace'] = workspace
        except Exception:
            values.update({'workspaces': [], 'workspace': None})
            workspace = None

        # Paginated transactions
        PER_PAGE = 30
        values['transactions'] = []
        values['review_items'] = []
        values['total_pages'] = 1
        values['current_page'] = page

        if workspace:
            try:
                txn_model = request.env['mumtaz.cfo.transaction']
                total = txn_model.search_count([('workspace_id', '=', workspace.id)])
                values['total_pages'] = max(1, (total + PER_PAGE - 1) // PER_PAGE)
                values['transactions'] = txn_model.search(
                    [('workspace_id', '=', workspace.id)],
                    order='date desc, id desc',
                    offset=(page - 1) * PER_PAGE,
                    limit=PER_PAGE,
                )
                values['review_items'] = request.env['mumtaz.cfo.review.item'].search(
                    [('transaction_id.workspace_id', '=', workspace.id),
                     ('status', '=', 'open')],
                    limit=20,
                )
                values['categories'] = request.env['mumtaz.cfo.category'].search(
                    [('workspace_id', '=', workspace.id)]
                )

                # Summary stats
                income_total = sum(
                    t.amount for t in txn_model.search([
                        ('workspace_id', '=', workspace.id), ('direction', '=', 'in')
                    ])
                )
                expense_total = sum(
                    t.amount for t in txn_model.search([
                        ('workspace_id', '=', workspace.id), ('direction', '=', 'out')
                    ])
                )
                values['income_total'] = income_total
                values['expense_total'] = expense_total
                values['net_total'] = income_total - expense_total
                values['review_open_count'] = request.env['mumtaz.cfo.review.item'].search_count(
                    [('transaction_id.workspace_id', '=', workspace.id), ('status', '=', 'open')]
                )
            except Exception as exc:
                _logger.warning("CFO portal data error: %s", exc)
                values.update({'transactions': [], 'review_items': [], 'categories': []})

        return request.render('mumtaz_portal.portal_cfo', values)

    @http.route('/mumtaz/cfo/upload', type='http', auth='user', website=True, methods=['POST'])
    def portal_cfo_upload(self, workspace_id=None, upload_file=None, **kw):
        """Handle CSV transaction file upload."""
        try:
            workspace = None
            if workspace_id:
                workspace = request.env['mumtaz.cfo.workspace'].browse(int(workspace_id))
                if not workspace.exists() or workspace.company_id.id != request.env.company.id:
                    workspace = None
            if not workspace:
                workspace = _get_cfo_workspace()
            if not workspace:
                return request.redirect('/mumtaz/cfo?error=no_workspace')

            if not upload_file:
                return request.redirect(f'/mumtaz/cfo?workspace_id={workspace.id}&error=no_file')

            file_data = upload_file.read()
            filename = upload_file.filename or 'upload.csv'

            # Find or create a data source for portal uploads
            data_source = request.env['mumtaz.cfo.data.source'].search(
                [('workspace_id', '=', workspace.id), ('source_type', '=', 'manual')],
                limit=1
            )
            if not data_source:
                data_source = request.env['mumtaz.cfo.data.source'].create({
                    'name': 'Portal Upload',
                    'workspace_id': workspace.id,
                    'source_type': 'manual',
                })

            # Create upload batch
            batch = request.env['mumtaz.cfo.upload.batch'].create({
                'data_source_id': data_source.id,
                'file_name': filename,
                'file_data': base64.b64encode(file_data).decode(),
                'status': 'pending',
            })

            # Trigger ingestion
            try:
                batch.action_process()
            except Exception as exc:
                _logger.warning("CFO ingestion failed: %s", exc)

            return request.redirect(f'/mumtaz/cfo?workspace_id={workspace.id}&uploaded=1')
        except Exception as exc:
            _logger.exception("CFO upload error: %s", exc)
            return request.redirect('/mumtaz/cfo?error=upload_failed')

    @http.route('/mumtaz/cfo/workspace/create', type='json', auth='user', csrf=False)
    def portal_cfo_create_workspace(self, name, **kw):
        """Create a new CFO workspace for the current company."""
        try:
            import re
            code = re.sub(r'[^A-Z0-9]', '', (name or 'WS').upper())[:8] or 'WS1'
            # Ensure unique code
            existing = request.env['mumtaz.cfo.workspace'].search(
                [('company_id', '=', request.env.company.id), ('code', '=', code)]
            )
            if existing:
                code = code[:6] + str(existing.id)[-2:]

            workspace = request.env['mumtaz.cfo.workspace'].create({
                'name': name,
                'code': code,
                'company_id': request.env.company.id,
                'owner_user_id': request.env.user.id,
            })
            return {'success': True, 'workspace_id': workspace.id, 'name': workspace.name}
        except Exception as exc:
            return {'error': str(exc)}

    # ──────────────────────────────────────────────────────────────────
    # Finance Hub
    # ──────────────────────────────────────────────────────────────────

    @http.route('/mumtaz/finance', type='http', auth='user', website=True)
    def portal_finance(self, **kw):
        values = _base_values('finance')
        workspace = _get_cfo_workspace()
        values['workspace'] = workspace

        # Compute a simple credit readiness score (0–100) based on operational signals
        score = 0
        score_factors = []

        profile = values.get('sme_profile')
        if profile:
            score += 20
            score_factors.append(('SME Profile', 20, True))
        else:
            score_factors.append(('SME Profile', 20, False))

        onboarding = values.get('onboarding')
        if onboarding and onboarding.progress >= 75:
            score += 15
            score_factors.append(('Onboarding Complete', 15, True))
        else:
            score_factors.append(('Onboarding Progress', 15, onboarding and onboarding.progress >= 50))

        if workspace:
            try:
                txn_count = request.env['mumtaz.cfo.transaction'].search_count(
                    [('workspace_id', '=', workspace.id)]
                )
                if txn_count >= 50:
                    score += 30
                    score_factors.append(('Transaction History (50+)', 30, True))
                elif txn_count >= 10:
                    score += 15
                    score_factors.append(('Transaction History (10+)', 30, True))
                else:
                    score_factors.append(('Transaction History', 30, False))

                review_count = request.env['mumtaz.cfo.review.item'].search_count(
                    [('transaction_id.workspace_id', '=', workspace.id), ('status', '=', 'open')]
                )
                if review_count == 0:
                    score += 15
                    score_factors.append(('No Pending Reviews', 15, True))
                else:
                    score_factors.append(('Pending Review Items', 15, False))
            except Exception:
                score_factors.append(('CFO Data', 45, False))
        else:
            score_factors.append(('CFO Workspace', 45, False))

        ai_sessions = 0
        try:
            ai_sessions = request.env['mumtaz.ai.session'].search_count(
                [('company_id', '=', request.env.company.id)]
            )
        except Exception:
            pass
        if ai_sessions >= 3:
            score += 20
            score_factors.append(('AI Engagement', 20, True))
        else:
            score_factors.append(('AI Engagement', 20, False))

        values['credit_score'] = score
        values['score_factors'] = score_factors
        values['score_band'] = (
            'excellent' if score >= 80 else
            'strong' if score >= 60 else
            'building' if score >= 35 else
            'early'
        )

        # Partner offers (placeholder — real matching would query partner DB)
        values['partner_offers'] = _get_finance_offers(score)

        return request.render('mumtaz_portal.portal_finance', values)

    # ──────────────────────────────────────────────────────────────────
    # Onboarding Wizard
    # ──────────────────────────────────────────────────────────────────

    @http.route('/mumtaz/onboard', type='http', auth='user', website=True)
    def portal_onboard(self, step=None, **kw):
        values = _base_values('onboard')
        profile = values.get('sme_profile')
        onboarding = values.get('onboarding')
        values['step'] = step or (onboarding.onboarding_stage if onboarding else 'profile')
        values['country_ids'] = request.env['res.country'].search([])
        values['industry_options'] = [
            ('retail', 'Retail & Trading'), ('manufacturing', 'Manufacturing'),
            ('services', 'Professional Services'), ('food_beverage', 'Food & Beverage'),
            ('technology', 'Technology'), ('healthcare', 'Healthcare'),
            ('construction', 'Construction & Real Estate'), ('logistics', 'Logistics & Transport'),
            ('education', 'Education'), ('finance', 'Finance & Insurance'),
            ('hospitality', 'Hospitality & Tourism'), ('other', 'Other'),
        ]
        return request.render('mumtaz_portal.portal_onboard', values)

    @http.route('/mumtaz/onboard/save', type='json', auth='user', csrf=False)
    def portal_onboard_save(self, step, data, **kw):
        """Save onboarding step data."""
        try:
            company = request.env.company
            profile = _get_sme_profile()

            if step == 'profile':
                profile_vals = {
                    'company_id': company.id,
                    'legal_name': data.get('legal_name') or company.name,
                    'trade_name': data.get('trade_name', ''),
                    'industry': data.get('industry', 'other'),
                    'business_type': data.get('business_type', 'llc'),
                    'city': data.get('city', ''),
                }
                country_id = data.get('country_id')
                if country_id:
                    profile_vals['country_id'] = int(country_id)

                if profile:
                    profile.write(profile_vals)
                else:
                    profile = request.env['mumtaz.sme.profile'].create(profile_vals)

                # Create / update onboarding checklist
                onboarding = _get_onboarding()
                if not onboarding:
                    onboarding = request.env['mumtaz.onboarding.checklist'].create({
                        'company_id': company.id,
                        'sme_profile_id': profile.id,
                    })
                onboarding.write({'task_company_info': True, 'sme_profile_id': profile.id})

                return {'success': True, 'next_step': 'finance', 'progress': onboarding.progress}

            elif step == 'finance':
                onboarding = _get_onboarding()
                if onboarding:
                    onboarding.write({'task_bank_connected': True})

                # Create workspace if requested
                workspace_name = data.get('workspace_name', f"{company.name} – CFO")
                workspace = _get_cfo_workspace()
                if not workspace:
                    import re
                    code = re.sub(r'[^A-Z0-9]', '', company.name.upper())[:6] or 'CFO'
                    workspace = request.env['mumtaz.cfo.workspace'].create({
                        'name': workspace_name,
                        'code': code,
                        'company_id': company.id,
                        'owner_user_id': request.env.user.id,
                    })

                return {'success': True, 'next_step': 'ai', 'workspace_id': workspace.id,
                        'progress': onboarding.progress if onboarding else 25}

            elif step == 'ai':
                onboarding = _get_onboarding()
                if onboarding:
                    onboarding.write({'task_crm_leads': True})
                return {'success': True, 'next_step': 'complete',
                        'progress': onboarding.progress if onboarding else 75}

            elif step == 'complete':
                onboarding = _get_onboarding()
                if onboarding:
                    onboarding.write({'task_crm_pipeline': True})
                return {'success': True, 'redirect': '/mumtaz/dashboard',
                        'progress': onboarding.progress if onboarding else 100}

            return {'error': f'Unknown step: {step}'}
        except Exception as exc:
            _logger.exception("Onboarding save error (step=%s): %s", step, exc)
            return {'error': str(exc)}

    # ──────────────────────────────────────────────────────────────────
    # Profile / Settings
    # ──────────────────────────────────────────────────────────────────

    @http.route('/mumtaz/profile', type='http', auth='user', website=True)
    def portal_profile(self, **kw):
        values = _base_values('profile')
        values['industry_options'] = [
            ('retail', 'Retail & Trading'), ('manufacturing', 'Manufacturing'),
            ('services', 'Professional Services'), ('food_beverage', 'Food & Beverage'),
            ('technology', 'Technology'), ('healthcare', 'Healthcare'),
            ('construction', 'Construction & Real Estate'), ('logistics', 'Logistics & Transport'),
            ('education', 'Education'), ('finance', 'Finance & Insurance'),
            ('hospitality', 'Hospitality & Tourism'), ('other', 'Other'),
        ]
        return request.render('mumtaz_portal.portal_profile', values)

    @http.route('/mumtaz/profile/save', type='json', auth='user', csrf=False)
    def portal_profile_save(self, data, **kw):
        try:
            profile = _get_sme_profile()
            vals = {k: v for k, v in data.items() if k in (
                'legal_name', 'trade_name', 'industry', 'business_type', 'city',
                'tax_number', 'employee_count', 'annual_revenue_band',
            )}
            if 'country_id' in data and data['country_id']:
                vals['country_id'] = int(data['country_id'])

            if profile:
                profile.write(vals)
            else:
                vals['company_id'] = request.env.company.id
                profile = request.env['mumtaz.sme.profile'].create(vals)

            return {'success': True}
        except Exception as exc:
            return {'error': str(exc)}


# ── Finance offer helper ───────────────────────────────────────────────

def _get_finance_offers(score: int) -> list:
    """Return indicative finance offers based on credit readiness score."""
    offers = []
    if score >= 60:
        offers.append({
            'title': 'SME Working Capital Finance',
            'provider': 'Partner Bank Network',
            'amount': 'Up to AED 500,000',
            'rate': 'From 8% p.a.',
            'badge': 'Best Match',
            'badge_class': 'badge-indigo',
            'icon': '🏦',
        })
        offers.append({
            'title': 'Invoice Financing',
            'provider': 'Fintech Partners',
            'amount': 'Up to 90% of invoice value',
            'rate': 'Flat 1.5% / 30 days',
            'badge': 'Popular',
            'badge_class': 'badge-teal',
            'icon': '🧾',
        })
    if score >= 35:
        offers.append({
            'title': 'Business Credit Line',
            'provider': 'Digital Banking Partners',
            'amount': 'AED 50,000 – 200,000',
            'rate': 'From 12% p.a.',
            'badge': 'Available',
            'badge_class': 'badge-emerald',
            'icon': '💳',
        })
    if score < 60:
        offers.append({
            'title': 'Build Your Credit Profile',
            'provider': 'Mumtaz Finance',
            'amount': 'Complete onboarding to unlock',
            'rate': 'Improve your readiness score',
            'badge': 'Recommended',
            'badge_class': 'badge-gold',
            'icon': '📈',
        })
    return offers
