from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .secret_guard import refuse_secret

# The documents onboarding normally needs. A starting list the PM edits, not a
# rule: a row can be marked not applicable with a reason.
STANDARD_DOCUMENTS = [
    ("contract", "Signed contract or approved order"),
    ("nda", "NDA / confidentiality agreement"),
    ("trade_licence", "Trade licence"),
    ("tax_registration", "Tax registration certificate"),
    ("master_data", "Master-data request workbook"),
    ("authorised_signatory", "Authorised signatory confirmation"),
]


class C2pClientDocument(models.Model):
    _name = "c2p.client.document"
    _description = "C2P Client Required Document"
    _order = "partner_id, sequence, id"

    name = fields.Char(string="Document", required=True)
    code = fields.Char(readonly=True, copy=False)
    sequence = fields.Integer(default=10)
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, index=True,
        ondelete="cascade", domain="[('c2p_is_client', '=', True)]")
    # Empty by default: a client is shared by Consultants and Solutions, and
    # the Solutions delivery owner must see what Consultants recorded. Set a
    # company to restrict a row to it.
    company_id = fields.Many2one("res.company", index=True)
    state = fields.Selection(
        [("required", "Required"), ("requested", "Requested"),
         ("received", "Received"), ("verified", "Verified"),
         ("na", "Not applicable")],
        string="Status", default="required", required=True, index=True)
    location = fields.Char(
        string="Where it is kept",
        help="A document reference or folder path. Not the document's content.")
    # Stored as an Odoo attachment (in the filestore, not in the table), and
    # readable by whoever may read the row.
    file = fields.Binary(string="File", attachment=True, copy=False)
    file_name = fields.Char(string="File Name", copy=False)
    received_on = fields.Date()
    na_reason = fields.Char(string="Reason not applicable")
    owner_id = fields.Many2one(
        "res.users", string="C2P Owner", default=lambda self: self.env.user)

    _partner_code_unique = models.Constraint(
        "UNIQUE(partner_id, code)",
        "This client already has that standard document.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._c2p_mark_received(vals, current_state=vals.get("state", "required"))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("file") and "state" not in vals:
            # Uploading the file is the document arriving. Rows still waiting
            # move to Received; rows already verified or marked not applicable
            # are left as their owner set them.
            waiting = self.filtered(lambda d: d.state in ("required", "requested"))
            if waiting:
                extra = dict(vals)
                self._c2p_mark_received(extra, current_state="required")
                super(C2pClientDocument, waiting).write(extra)
                return super(C2pClientDocument, self - waiting).write(vals)
        return super().write(vals)

    @api.model
    def _c2p_mark_received(self, vals, current_state):
        if vals.get("file") and current_state in ("required", "requested"):
            vals["state"] = "received"
            vals.setdefault("received_on", fields.Date.context_today(self))

    @api.constrains("state", "na_reason")
    def _check_na_reason(self):
        for doc in self:
            if doc.state == "na" and not (doc.na_reason or "").strip():
                raise ValidationError(_(
                    "'%s' needs a reason to be marked not applicable.",
                    doc.name))

    @api.constrains("name", "location", "na_reason", "file_name")
    def _check_no_secret(self):
        for doc in self:
            for fname in ("name", "location", "na_reason", "file_name"):
                refuse_secret(doc._fields[fname].string, doc[fname])
