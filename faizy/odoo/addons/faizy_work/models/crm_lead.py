from odoo import api, fields, models
from odoo.exceptions import ValidationError

PROSPECT_STATUS = [
    ('research', 'Research Candidate'),
    ('verified', 'Verified Prospect'),
    ('contacted', 'Contacted'),
    ('engaged', 'Engaged'),
    ('qualified', 'Qualified Opportunity'),
    ('trial', 'Trial / First Service'),
    ('paying', 'Paying Customer'),
]
RANK = {key: i for i, (key, _label) in enumerate(PROSPECT_STATUS)}

# Prospect status -> the production CRM stage. The stages themselves are
# standard Odoo and are not renamed, added or removed.
STATUS_STAGE_XMLID = {
    'research': 'crm.stage_lead1', 'verified': 'crm.stage_lead1',
    'contacted': 'crm.stage_lead1', 'engaged': 'crm.stage_lead1',
    'qualified': 'crm.stage_lead2', 'trial': 'crm.stage_lead3', 'paying': 'crm.stage_lead4',
}
STAGE_STATUS = {  # first status of each stage, used when a card is dragged
    'crm.stage_lead1': 'research', 'crm.stage_lead2': 'qualified',
    'crm.stage_lead3': 'trial', 'crm.stage_lead4': 'paying',
}
STATUS_DATE_FIELD = {
    'verified': 'faizy_verified_on', 'contacted': 'faizy_contacted_on',
    'engaged': 'faizy_engaged_on', 'qualified': 'faizy_qualified_on',
}
MARKETING_SOURCES = ('facebook', 'instagram', 'website', 'whatsapp')
ROUTE_PARAM = 'faizy.work_route_leads'


class CrmLead(models.Model):
    _name = 'crm.lead'
    _inherit = ['crm.lead', 'mail.thread', 'faizy.checklist.mixin']

    faizy_originator_id = fields.Many2one(
        'res.users', string='Originator', copy=False, index=True, tracking=True,
        default=lambda self: self.env.user,
        help='Who found this prospect. The salesperson (owner) can change later; the originator does not.')
    faizy_prospect_status = fields.Selection(
        PROSPECT_STATUS, string='Prospect status', default='research', tracking=True, index=True)
    faizy_prospect_kind = fields.Selection(
        [('organisation', 'Organisation'), ('individual', 'Individual')],
        string='Prospect type', default='organisation')
    faizy_contact_basis = fields.Selection([
        ('inquiry', 'They contacted FAIZY (inquiry)'),
        ('opt_in', 'Opted in'),
        ('public_business', 'Public business contact'),
        ('referral', 'Referral'),
    ], string='Legitimate contact basis')
    faizy_evidence_url = fields.Char(string='Source / evidence link')
    faizy_verified_on = fields.Date(string='Verified on', copy=False)
    faizy_verified_by = fields.Many2one('res.users', string='Verified by', copy=False)
    faizy_contacted_on = fields.Date(copy=False)
    faizy_engaged_on = fields.Date(copy=False)
    faizy_qualified_on = fields.Date(copy=False)
    faizy_duplicate_reviewed = fields.Boolean(
        string='Duplicates reviewed', copy=False,
        help='Tick after looking at the duplicate list and deciding this is a separate prospect.')
    faizy_duplicate_count = fields.Integer(compute='_compute_duplicates', string='Possible duplicates')

    # ── duplicates ───────────────────────────────────────────────────────
    def _duplicate_domain(self):
        self.ensure_one()
        clauses = []
        if self.email_normalized:
            clauses.append([('email_normalized', '=', self.email_normalized)])
        if self.phone_sanitized:
            clauses.append([('phone_sanitized', '=', self.phone_sanitized)])
        if self.partner_name and self.partner_name.strip():
            clauses.append([('partner_name', '=ilike', self.partner_name.strip())])
        if self.faizy_evidence_url:
            clauses.append([('faizy_evidence_url', '=', self.faizy_evidence_url)])
        if not clauses:
            return None
        domain = clauses[0]
        for extra in clauses[1:]:
            domain = ['|'] + domain + extra
        return [('id', '!=', self.id), ('active', 'in', (True, False))] + domain

    def _find_duplicates(self):
        self.ensure_one()
        domain = self._duplicate_domain()
        return self.sudo().search(domain) if domain else self.browse()

    def _compute_duplicates(self):
        for lead in self:
            lead.faizy_duplicate_count = len(lead._find_duplicates()) if lead.id else 0

    def action_view_duplicates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Possible duplicates'),
            'res_model': 'crm.lead', 'view_mode': 'list,form',
            'domain': [('id', 'in', self._find_duplicates().ids)],
            'context': {'active_test': False},
        }

    # ── verification and status rules ────────────────────────────────────
    def _verification_problems(self):
        self.ensure_one()
        problems = []
        if not self.user_id:
            problems.append(self.env._('an owner (Salesperson)'))
        if self.faizy_prospect_kind == 'individual':
            if not self.faizy_contact_basis:
                problems.append(self.env._('a legitimate contact basis (inquiry, opt-in, referral)'))
        else:
            if not (self.partner_name or '').strip():
                problems.append(self.env._('the organisation name'))
            if not (self.faizy_evidence_url or '').strip():
                problems.append(self.env._('a source / evidence link'))
            if not self.faizy_contact_basis:
                problems.append(self.env._('a legitimate contact basis'))
        if not self.activity_ids:
            problems.append(self.env._('a next action (schedule an activity with a due date)'))
        if self._find_duplicates() and not self.faizy_duplicate_reviewed:
            problems.append(self.env._('a duplicate review (see Possible duplicates)'))
        return problems

    def _status_requirements(self, status):
        """Everything that must be true to sit at this status. Evaluated only
        when a lead moves up, so existing leads are not touched."""
        self.ensure_one()
        if RANK[status] >= RANK['verified']:
            problems = self._verification_problems()
            if problems:
                raise ValidationError(self.env._(
                    '%(lead)s cannot be %(st)s yet. Missing: %(m)s.',
                    lead=self.display_name, st=dict(PROSPECT_STATUS)[status], m='; '.join(problems)))
            self._checklist_gate('verify', require_existing=True, what=self.env._('verify the prospect'))
        if RANK[status] >= RANK['qualified']:
            self._checklist_gate('qualify', require_existing=True, what=self.env._('qualify the lead'))
        if status == 'paying':
            partner = self.partner_id.sudo()
            paid = partner and (
                partner.faizy_subscription_id or self.env['faizy.order'].sudo().search_count(
                    [('partner_id', '=', partner.id), ('state', '=', 'completed')]))
            if not paid:
                raise ValidationError(self.env._(
                    '%s is not a Paying Customer yet: the contact needs a live subscription or a completed order.',
                    self.display_name))

    # ── create / write ───────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            status = vals.get('faizy_prospect_status')
            if status and RANK.get(status, 0) > RANK['research'] and self._checklist_enforced():
                # A lead may be created as research candidate only: the rest is earned.
                vals['faizy_prospect_status'] = 'research'
        leads = super().create(vals_list)
        leads._faizy_route_new()
        return leads

    def write(self, vals):
        enforced = self._checklist_enforced()
        vals = dict(vals)
        # A kanban drag on the stage becomes a status move, so it meets the same gates.
        if 'stage_id' in vals and 'faizy_prospect_status' not in vals and vals['stage_id'] and enforced:
            target = self.env['crm.stage'].browse(vals['stage_id'])
            for xmlid, status in STAGE_STATUS.items():
                if self.env.ref(xmlid, raise_if_not_found=False) == target:
                    if self and all(RANK.get(ln.faizy_prospect_status or 'research', 0) < RANK[status]
                                    for ln in self):
                        vals['faizy_prospect_status'] = status
                    break
        new_status = vals.get('faizy_prospect_status')
        if new_status:
            today = fields.Date.context_today(self)
            for lead in self:
                old = lead.faizy_prospect_status or 'research'
                if RANK[new_status] > RANK[old] and enforced:
                    lead._status_requirements(new_status)
            if len(self) and all(RANK[new_status] > RANK[ln.faizy_prospect_status or 'research'] for ln in self):
                xmlid = STATUS_STAGE_XMLID[new_status]
                stage = self.env.ref(xmlid, raise_if_not_found=False)
                if stage and 'stage_id' not in vals:
                    vals['stage_id'] = stage.id
            res = super().write(vals)
            for lead in self:
                extra = {}
                field = STATUS_DATE_FIELD.get(new_status)
                if field and not lead[field]:
                    extra[field] = today
                if new_status == 'verified' and not lead.faizy_verified_by:
                    extra['faizy_verified_by'] = self.env.user.id
                if extra:
                    super(CrmLead, lead).write(extra)
            return res
        return super().write(vals)

    # ── routing of new leads (off until the founder approves) ────────────
    def _faizy_route_new(self):
        if self.env['ir.config_parameter'].sudo().get_param(ROUTE_PARAM) != 'on':
            return
        routing = self.env['faizy.routing']
        for lead in self:
            if lead.user_id and lead.user_id != self.env.ref('base.user_root') and \
                    lead.user_id.id != self.env.uid:
                continue
            role = 'care' if lead.faizy_lead_source in MARKETING_SOURCES else 'ops'
            owner = routing._role_user(role)
            lead.sudo().with_context(mail_notrack=True).write({'user_id': owner.id})
