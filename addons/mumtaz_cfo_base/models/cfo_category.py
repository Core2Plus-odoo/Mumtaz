from odoo import api, fields, models


class MumtazCFOCategory(models.Model):
    _name = "mumtaz.cfo.category"
    _description = "Mumtaz CFO Category"
    _order = "kind, name"
    _check_company_auto = True

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    kind = fields.Selection(
        [
            ("income", "Income"),
            ("expense", "Expense"),
            ("transfer", "Transfer"),
            ("other", "Other"),
        ],
        default="expense",
        required=True,
    )
    workspace_id = fields.Many2one("mumtaz.cfo.workspace", ondelete="cascade", index=True)
    company_id = fields.Many2one(
        "res.company",
        required=False,
        index=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    is_system = fields.Boolean(
        default=False,
        readonly=True,
        help="System categories are template categories used to initialize new workspaces.",
    )

    _sql_constraints = [
        (
            "mumtaz_cfo_category_workspace_code_unique",
            "unique(workspace_id, code)",
            "Category code must be unique within a workspace.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = self._sanitize_code(vals["code"])
            elif vals.get("name"):
                vals["code"] = self._sanitize_code(vals["name"])

            workspace_id = vals.get("workspace_id")
            if workspace_id and not vals.get("company_id"):
                workspace = self.env["mumtaz.cfo.workspace"].browse(workspace_id)
                vals["company_id"] = workspace.company_id.id

            if not workspace_id:
                vals["company_id"] = False
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = self._sanitize_code(vals["code"])
        return super().write(vals)

    @staticmethod
    def _sanitize_code(value):
        return "_".join((value or "").strip().lower().replace("-", " ").split())
