import base64
import csv
import io
import json
from odoo import fields, models
from odoo.exceptions import UserError


class MumtazCFOUploadBatch(models.Model):
    _name = "mumtaz.cfo.upload.batch"
    _description = "Mumtaz CFO Upload Batch"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    name = fields.Char(required=True, default="New Upload Batch", tracking=True)
    workspace_id = fields.Many2one(
        "mumtaz.cfo.workspace",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    company_id = fields.Many2one(related="workspace_id.company_id", store=True, index=True, readonly=True)
    data_source_id = fields.Many2one(
        "mumtaz.cfo.data.source",
        required=True,
        ondelete="restrict",
        domain="[('workspace_id', '=', workspace_id)]",
        tracking=True,
    )
    mapping_profile_id = fields.Many2one(
        "mumtaz.cfo.mapping.profile",
        domain="[('workspace_id', '=', workspace_id)]",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("uploaded", "Uploaded"),
            ("mapped", "Mapped"),
            ("ready", "Ready"),
            ("failed", "Failed"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )
    upload_file = fields.Binary(required=True, attachment=True)
    upload_filename = fields.Char(required=True)
    file_type = fields.Selection(
        [("csv", "CSV"), ("xlsx", "Excel (.xlsx)"), ("xls", "Excel (.xls)"), ("unknown", "Unknown")],
        default="unknown",
        readonly=True,
    )
    uploaded_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    uploaded_on = fields.Datetime(default=fields.Datetime.now, readonly=True)
    preview_json = fields.Text(readonly=True)
    preview_line_count = fields.Integer(readonly=True)
    detected_columns = fields.Char(readonly=True)
    row_count = fields.Integer(readonly=True)
    error_message = fields.Text(readonly=True)

    def action_set_uploaded(self):
        for rec in self:
            if not rec.upload_file:
                raise UserError("Upload file is required.")
            rec.write(
                {
                    "file_type": rec._detect_file_type(rec.upload_filename),
                    "state": "uploaded",
                    "error_message": False,
                    "uploaded_on": fields.Datetime.now(),
                    "uploaded_by": self.env.user.id,
                }
            )
        return True

    def action_generate_preview(self):
        for rec in self:
            rec.action_set_uploaded()
            if rec.file_type != "csv":
                rec.write(
                    {
                        "preview_json": json.dumps([], ensure_ascii=False),
                        "preview_line_count": 0,
                        "detected_columns": False,
                        "state": "uploaded",
                        "error_message": (
                            "Preview currently supports CSV files only. "
                            "Excel preview foundation will be added in a later phase."
                        ),
                    }
                )
                continue

            rows, headers = rec._csv_preview_rows(max_rows=20)
            rec.write(
                {
                    "preview_json": json.dumps(rows, ensure_ascii=False),
                    "preview_line_count": len(rows),
                    "detected_columns": ", ".join(headers),
                    "row_count": len(rows),
                    "state": "uploaded",
                    "error_message": False,
                }
            )
        return True

    def action_mark_mapped(self):
        for rec in self:
            if not rec.mapping_profile_id:
                raise UserError("Mapping profile is required before marking the batch as mapped.")
            rec.write({"state": "mapped", "error_message": False})
        return True

    def action_mark_ready(self):
        for rec in self:
            if rec.state not in ("mapped", "uploaded"):
                raise UserError("Batch must be uploaded or mapped before marking ready.")
            rec.write({"state": "ready", "error_message": False})
        return True

    def _csv_preview_rows(self, max_rows=20):
        self.ensure_one()
        payload = base64.b64decode(self.upload_file or b"")
        if not payload:
            raise UserError("Uploaded file is empty.")

        candidates = ["utf-8-sig", "utf-8", "latin-1"]
        decoded = None
        for enc in candidates:
            try:
                decoded = payload.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise UserError("Could not decode CSV file.")

        reader = csv.DictReader(io.StringIO(decoded))
        headers = reader.fieldnames or []
        rows = []
        for index, row in enumerate(reader):
            if index >= max_rows:
                break
            rows.append({k: (v or "").strip() for k, v in (row or {}).items()})
        return rows, headers

    @staticmethod
    def _detect_file_type(filename):
        value = (filename or "").lower()
        if value.endswith(".csv"):
            return "csv"
        if value.endswith(".xlsx"):
            return "xlsx"
        if value.endswith(".xls"):
            return "xls"
        return "unknown"
