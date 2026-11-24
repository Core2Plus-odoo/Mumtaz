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
    received_on = fields.Date()
    na_reason = fields.Char(string="Reason not applicable")
    owner_id = fields.Many2one(
        "res.users", string="C2P Owner", default=lambda self: self.env.user)

    _partner_code_unique = models.Constraint(
        "UNIQUE(partner_id, code)",
        "This client already has that standard document.")

    @api.constrains("state", "na_reason")
    def _check_na_reason(self):
        for doc in self:
            if doc.state == "na" and not (doc.na_reason or "").strip():
                raise ValidationError(_(
                    "'%s' needs a reason to be marked not applicable.",
                    doc.name))

    @api.constrains("name", "location", "na_reason")
    def _check_no_secret(self):
        for doc in self:
            for fname in ("name", "location", "na_reason"):
                refuse_secret(doc._fields[fname].string, doc[fname])
