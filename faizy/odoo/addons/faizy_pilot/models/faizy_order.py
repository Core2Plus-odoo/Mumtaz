from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# Context values are client-controllable: an RPC caller can send any JSON in
# `context`. A plain True/string flag would therefore let any staff user skip
# the gate. This module-level object cannot be serialised by a client, so a
# context entry equal to it can only have been set by code in this process.
_TOKEN = object()

EVIDENCE_STATES = [
    ("none", "No evidence"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]

# Written only by the action methods below, never straight from a client.
_PROTECTED = {
    "evidence_state",
    "evidence_reviewer_id",
    "evidence_reviewed_on",
    "evidence_exception_by",
}


class FaizyOrder(models.Model):
    _inherit = "faizy.order"

    # The images are evidence under review, not customer content. Staff-only
    # at field level; customers get approved images through the
    # /faizy/evidence route, which checks the order record rule first.
    proof_image = fields.Image(groups="faizy_core.group_faizy_user")
    receipt_image = fields.Image(groups="faizy_core.group_faizy_user")

    evidence_state = fields.Selection(
        EVIDENCE_STATES, default="none", copy=False, tracking=True, index=True
    )
    evidence_reviewer_id = fields.Many2one("res.users", copy=False, readonly=True)
    evidence_reviewed_on = fields.Datetime(copy=False, readonly=True)
    evidence_reject_reason = fields.Text(copy=False)
    evidence_exception_reason = fields.Text(copy=False)
    evidence_exception_by = fields.Many2one("res.users", copy=False, readonly=True)

    # What a customer is allowed to know exists. Computed with sudo because the
    # customer cannot read the image fields themselves.
    proof_visible = fields.Boolean(compute="_compute_evidence_visible", compute_sudo=True)
    receipt_visible = fields.Boolean(compute="_compute_evidence_visible", compute_sudo=True)

    @api.depends("evidence_state", "proof_image", "receipt_image")
    def _compute_evidence_visible(self):
        for order in self:
            approved = order.evidence_state == "approved"
            order.proof_visible = approved and bool(order.proof_image)
            order.receipt_visible = approved and bool(order.receipt_image)

    # ── helpers ──────────────────────────────────────────────────────────
    def _evidence_missing(self):
        """What is still needed before this order may complete (sudo read)."""
        self.ensure_one()
        order = self.sudo()
        missing = []
        if not order.proof_image:
            missing.append(self.env._("proof photo"))
        if order.purchase_value > 0 and not order.receipt_image:
            missing.append(self.env._("receipt photo"))
        return missing

    def _check_completion_evidence(self):
        problems = []
        for order in self:
            missing = order._evidence_missing()
            if missing:
                problems.append(
                    self.env._("%(order)s: missing %(what)s", order=order.display_name,
                               what=", ".join(missing))
                )
            elif order.evidence_state != "approved":
                problems.append(
                    self.env._("%(order)s: evidence is %(state)s, not approved",
                               order=order.display_name, state=order.evidence_state)
                )
        if problems:
            raise ValidationError(
                self.env._("Cannot complete without approved evidence.\n%s", "\n".join(problems))
            )

    def _require_group(self, xmlid):
        if not self.env.user.has_group(xmlid):
            raise AccessError(self.env._("You are not allowed to do this."))

    # ── create / write protection ────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if _PROTECTED & set(vals):
                raise AccessError(self.env._("Evidence review fields cannot be set directly."))
            if vals.get("proof_image") or vals.get("receipt_image"):
                vals["evidence_state"] = "submitted"
        return super().create(vals_list)

    def write(self, vals):
        internal = self.env.context.get("faizy_evidence_internal") is _TOKEN
        if _PROTECTED & set(vals) and not internal:
            raise AccessError(self.env._("Evidence review fields cannot be set directly."))
        # A kanban drag or an RPC write to state=completed must not bypass the gate.
        if vals.get("state") == "completed" and self.env.context.get("faizy_gate_passed") is not _TOKEN:
            self.filtered(lambda o: o.state != "completed")._check_completion_evidence()
        touched = {"proof_image", "receipt_image"} & set(vals)
        res = super().write(vals)
        if touched and not internal:
            # New or changed evidence always goes back to review, even if it
            # had been approved: approval covers the images that were reviewed.
            for order in self.sudo():
                new = "submitted" if (order.proof_image or order.receipt_image) else "none"
                order.with_context(faizy_evidence_internal=_TOKEN).write({
                    "evidence_state": new,
                    "evidence_reviewer_id": False,
                    "evidence_reviewed_on": False,
                })
        return res

    # ── review actions ───────────────────────────────────────────────────
    def action_approve_evidence(self):
        self._require_group("faizy_core.group_faizy_ops")
        for order in self:
            if order.evidence_state != "submitted":
                raise UserError(self.env._("%s: only submitted evidence can be approved.", order.display_name))
            missing = order._evidence_missing()
            if missing:
                raise UserError(self.env._("%(order)s: missing %(what)s", order=order.display_name,
                                           what=", ".join(missing)))
            order.with_context(faizy_evidence_internal=_TOKEN).write({
                "evidence_state": "approved",
                "evidence_reviewer_id": self.env.user.id,
                "evidence_reviewed_on": fields.Datetime.now(),
                "evidence_reject_reason": False,
            })
            order.message_post(body=self.env._("Evidence approved by %s.", self.env.user.name))
        return True

    def action_reject_evidence(self, reason=None):
        self._require_group("faizy_core.group_faizy_ops")
        for order in self:
            why = (reason or order.evidence_reject_reason or "").strip()
            if not why:
                raise UserError(self.env._("A reason is required to reject evidence."))
            if order.evidence_state not in ("submitted", "approved"):
                raise UserError(self.env._("%s: there is no evidence to reject.", order.display_name))
            order.with_context(faizy_evidence_internal=_TOKEN).write({
                "evidence_state": "rejected",
                "evidence_reviewer_id": self.env.user.id,
                "evidence_reviewed_on": fields.Datetime.now(),
                "evidence_reject_reason": why,
            })
            order.message_post(body=self.env._("Evidence rejected by %(user)s: %(why)s",
                                               user=self.env.user.name, why=why))
        return True

    # ── the gate ─────────────────────────────────────────────────────────
    def action_complete(self):
        # Runs before faizy_core's billing override (this class is loaded
        # last), so a refused completion never creates an invoice or wallet entry.
        if self.env.context.get("faizy_gate_passed") is not _TOKEN:
            self._check_completion_evidence()
        return super(FaizyOrder, self.with_context(faizy_gate_passed=_TOKEN)).action_complete()

    def action_complete_with_exception(self, reason=None):
        """Manager-only completion without approved evidence. Reason is mandatory and logged."""
        self._require_group("faizy_core.group_faizy_manager")
        for order in self:
            why = (reason or order.evidence_exception_reason or "").strip()
            if not why:
                raise UserError(self.env._("A written reason is required for an evidence exception."))
            order.with_context(faizy_evidence_internal=_TOKEN).write({
                "evidence_exception_reason": why,
                "evidence_exception_by": self.env.user.id,
            })
            order.message_post(body=self.env._(
                "Completed WITHOUT approved evidence by %(user)s. Reason: %(why)s",
                user=self.env.user.name, why=why))
        return super(FaizyOrder, self.with_context(faizy_gate_passed=_TOKEN)).action_complete()
