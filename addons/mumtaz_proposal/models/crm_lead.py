from odoo import api, fields, models, _


class CrmLead(models.Model):
    _inherit = "crm.lead"

    proposal_ids = fields.One2many(
        "mumtaz.proposal",
        "opportunity_id",
        string="Proposals",
    )
    proposal_count = fields.Integer(
        string="Proposals",
        compute="_compute_proposal_count",
    )

    @api.depends("proposal_ids")
    def _compute_proposal_count(self):
        for lead in self:
            lead.proposal_count = len(lead.proposal_ids)

    def action_view_proposals(self):
        self.ensure_one()
        action = {
            "name": _("Proposals"),
            "type": "ir.actions.act_window",
            "res_model": "mumtaz.proposal",
            "view_mode": "list,form",
            "domain": [("opportunity_id", "=", self.id)],
            "context": {
                "default_opportunity_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_user_id": self.user_id.id,
                "default_team_id": self.team_id.id,
            },
        }
        if self.proposal_count == 1:
            action["view_mode"] = "form"
            action["res_id"] = self.proposal_ids[0].id
        return action
