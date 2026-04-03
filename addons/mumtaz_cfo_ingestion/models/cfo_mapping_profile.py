import json

from odoo import fields, models
from odoo.exceptions import UserError


class MumtazCFOMappingProfile(models.Model):
    _name = "mumtaz.cfo.mapping.profile"
    _description = "Mumtaz CFO Mapping Profile"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True)
    workspace_id = fields.Many2one(
        "mumtaz.cfo.workspace",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(related="workspace_id.company_id", store=True, index=True, readonly=True)
    data_source_id = fields.Many2one(
        "mumtaz.cfo.data.source",
        ondelete="set null",
        domain="[('workspace_id', '=', workspace_id)]",
    )
    active = fields.Boolean(default=True)
    mapping_json = fields.Text(
        default='{"date":"date","description":"description","amount":"amount"}',
        help="JSON object describing how file columns map to normalized transaction fields.",
    )
    sample_columns = fields.Char(
        help="Comma separated source columns seen in a sample file for quick reference."
    )
    notes = fields.Text()

    def get_mapping_dict(self):
        self.ensure_one()
        try:
            value = json.loads(self.mapping_json or "{}")
        except json.JSONDecodeError as exc:
            raise UserError(f"Invalid mapping JSON for profile {self.name}: {exc}")
        if not isinstance(value, dict):
            raise UserError("Mapping JSON must be an object of target_field -> source_column.")
        return value
