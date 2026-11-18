import hashlib

from odoo import api, fields, models
from odoo.exceptions import UserError


class PharmaRawEvent(models.Model):
    """Immutable archive of every inbound partner payload (Blueprint s.3, s.22).

    The payload is stored exactly as received and can never be edited or deleted.
    Replays with the same (source, event_id) are ignored; the same id with a
    different payload is flagged as a conflict and never overwrites.
    """

    _name = "pharma.raw.event"
    _description = "Pharma Raw Source Event"
    _order = "id desc"
    _rec_name = "event_id"

    source = fields.Selection(
        [("shopify", "Shopify"), ("odoo_website", "Odoo Website"), ("partner", "Distribution Partner"),
         ("courier", "Courier"), ("gateway", "Payment Gateway"), ("bank", "Bank"),
         ("manual", "Manual / File Import")],
        required=True, readonly=True)
    event_id = fields.Char(string="Provider Event ID", required=True, readonly=True, index=True)
    payload = fields.Text(required=True, readonly=True)
    digest = fields.Char(compute="_compute_digest", store=True)
    state = fields.Selection(
        [("archived", "Archived"), ("posted", "Posted"), ("invalid", "Invalid"),
         ("conflict", "Conflict")], default="archived", required=True, readonly=True)
    error = fields.Char(readonly=True)
    is_demo = fields.Boolean(string="DEMO data", readonly=True)

    _sql_source_event_unique = models.Constraint(
        "unique(source, event_id)", "This source event already exists (replay ignored).")

    @api.depends("payload")
    def _compute_digest(self):
        for rec in self:
            rec.digest = hashlib.sha256((rec.payload or "").encode()).hexdigest()

    @api.model
    def ingest(self, source, event_id, payload, is_demo=False):
        """Idempotent ingest. Returns (record, outcome)."""
        existing = self.sudo().search([("source", "=", source), ("event_id", "=", event_id)], limit=1)
        if existing:
            if existing.digest != hashlib.sha256(payload.encode()).hexdigest():
                existing.sudo().with_context(pharma_internal=True).write(
                    {"state": "conflict", "error": "Same event id received with a different payload."})
                return existing, "conflict"
            return existing, "duplicate_ignored"
        rec = self.sudo().create({"source": source, "event_id": event_id,
                                  "payload": payload, "is_demo": is_demo})
        return rec, "archived"

    def write(self, vals):
        if not self.env.context.get("pharma_internal"):
            locked = {"source", "event_id", "payload"} & set(vals)
            if locked:
                raise UserError("Raw source events are immutable and cannot be edited.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Raw source events are immutable and cannot be deleted.")
