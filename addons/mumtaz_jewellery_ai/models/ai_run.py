from odoo import fields, models


class AiRun(models.Model):
    """One row per agent action: who asked, which tool at which level, model
    or local path, tokens, outcome. Refused and failed runs are rows too --
    a refusal is the control working and belongs in the record. Written
    under sudo by the agent so a run a user may not read (about a client she
    may not see) is still logged; reading follows the client's rule."""

    _name = 'jewellery.ai.run'
    _description = 'Jawhar AI run'
    _order = 'id desc'

    agent = fields.Selection([('zayan', 'Zayan'), ('layla', 'Layla')], required=True, index=True)
    tool = fields.Char(required=True, index=True)
    level = fields.Selection([('A', 'A read'), ('B', 'B recommend'), ('C', 'C draft'),
                              ('D', 'D execute'), ('E', 'E prohibited')], required=True)
    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    partner_id = fields.Many2one('res.partner', string='Client', index=True, ondelete='set null')
    draft_id = fields.Many2one('jewellery.ai.draft', ondelete='set null')
    status = fields.Selection([('done', 'Done'), ('refused', 'Refused'), ('failed', 'Failed')],
                              required=True, default='done', index=True)
    reason = fields.Char(help='Why it was refused or failed; a short code, never a payload.')
    model_used = fields.Char(required=True, default='local',
                             help="'local' for the deterministic path, else the model id.")
    input_tokens = fields.Integer()
    output_tokens = fields.Integer()
    duration_ms = fields.Integer()
    payload_digest = fields.Char(help='sha256 of what was sent to the model, when anything was.')
    sources = fields.Text(help='Which records and timestamps the answer was read from.')
    policy_version = fields.Char(required=True)
    request_text = fields.Char(help='The request as typed, for the command bar only.')
