from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MumtazCFOWorkspace(models.Model):
    _name = "mumtaz.cfo.workspace"
    _description = "Mumtaz CFO Workspace"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        required=True,
        tracking=True,
        help="Unique workspace code used in API and integrations.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    owner_user_id = fields.Many2one(
        "res.users",
        string="Workspace Owner",
        default=lambda self: self.env.user,
        required=True,
        check_company=True,
        tracking=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True, store=False)
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text()
    category_ids = fields.One2many("mumtaz.cfo.category", "workspace_id", string="Categories")
    category_count = fields.Integer(compute="_compute_category_count", string="Category Count")

    _sql_constraints = [
        (
            "mumtaz_cfo_workspace_company_code_unique",
            "unique(company_id, code)",
            "Workspace code must be unique per company.",
        ),
    ]

    @api.depends("category_ids")
    def _compute_category_count(self):
        for rec in self:
            rec.category_count = len(rec.category_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("owner_user_id", self.env.user.id)
            if vals.get("code"):
                vals["code"] = self._sanitize_code(vals["code"])
            elif vals.get("name"):
                vals["code"] = self._sanitize_code(vals["name"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = self._sanitize_code(vals["code"])
        return super().write(vals)

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or len(rec.code) < 3:
                raise ValidationError("Workspace code must be at least 3 characters.")

    @staticmethod
    def _sanitize_code(value):
        return "_".join((value or "").strip().lower().replace("-", " ").split())

    def action_load_default_categories(self):
        """Clone system categories into this workspace if missing by code."""
        template_categories = self.env["mumtaz.cfo.category"].search([
            ("is_system", "=", True),
            ("workspace_id", "=", False),
        ])
        for workspace in self:
            existing_codes = set(workspace.category_ids.mapped("code"))
            to_create = []
            for cat in template_categories:
                if cat.code in existing_codes:
                    continue
                to_create.append({
                    "name": cat.name,
                    "code": cat.code,
                    "kind": cat.kind,
                    "workspace_id": workspace.id,
                    "company_id": workspace.company_id.id,
                    "is_system": False,
                })
            if to_create:
                self.env["mumtaz.cfo.category"].create(to_create)
        return True

    def action_view_categories(self):
        self.ensure_one()
        return {
            "name": "Workspace Categories",
            "type": "ir.actions.act_window",
            "res_model": "mumtaz.cfo.category",
            "view_mode": "list,form",
            "domain": [("workspace_id", "=", self.id)],
            "context": {
                "default_workspace_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }
