from odoo import fields, models


class MumtazCFODataSource(models.Model):
    _name = "mumtaz.cfo.data.source"
    _description = "Mumtaz CFO Data Source"
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
    source_type = fields.Selection(
        [
            ("manual_upload", "Manual Upload"),
            ("bank_statement", "Bank Statement"),
            ("erp_export", "ERP Export"),
            ("api_feed", "API Feed"),
        ],
        default="manual_upload",
        required=True,
    )
    external_ref = fields.Char(help="External provider/source identifier if available.")
    active = fields.Boolean(default=True)
    notes = fields.Text()
    mapping_profile_id = fields.Many2one(
        "mumtaz.cfo.mapping.profile",
        string="Default Mapping Profile",
        domain="[('workspace_id', '=', workspace_id)]",
    )
    upload_batch_ids = fields.One2many("mumtaz.cfo.upload.batch", "data_source_id", string="Upload Batches")
    upload_batch_count = fields.Integer(compute="_compute_upload_batch_count")

    def _compute_upload_batch_count(self):
        for rec in self:
            rec.upload_batch_count = len(rec.upload_batch_ids)

    def action_view_upload_batches(self):
        self.ensure_one()
        return {
            "name": "Upload Batches",
            "type": "ir.actions.act_window",
            "res_model": "mumtaz.cfo.upload.batch",
            "view_mode": "list,form",
            "domain": [("data_source_id", "=", self.id)],
            "context": {
                "default_workspace_id": self.workspace_id.id,
                "default_data_source_id": self.id,
            },
        }
