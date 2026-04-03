from odoo import fields, models
from odoo.exceptions import UserError


class MumtazCFOUploadBatch(models.Model):
    _inherit = "mumtaz.cfo.upload.batch"

    state = fields.Selection(selection_add=[("processed", "Processed")], ondelete={"processed": "set default"})
    processed_on = fields.Datetime(readonly=True)
    transaction_count = fields.Integer(readonly=True)
    duplicate_count = fields.Integer(readonly=True)
    review_count = fields.Integer(readonly=True)

    def action_process_batch(self):
        for batch in self:
            if batch.state not in ("uploaded", "mapped", "ready"):
                raise UserError("Batch must be uploaded, mapped, or ready before processing.")
            result = self.env["mumtaz.cfo.ingestion.service"].process_upload_batch(batch)
            batch.write(
                {
                    "state": "processed",
                    "processed_on": fields.Datetime.now(),
                    "transaction_count": result.get("transaction_count", 0),
                    "duplicate_count": result.get("duplicate_count", 0),
                    "review_count": result.get("review_count", 0),
                    "error_message": False,
                }
            )
        return True
