from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Odoo 19 closes a task through project.task.state. The closed values are
# prefixed "1_" ("1_done", "1_canceled") while the open ones carry a numeric
# order prefix ("01_in_progress", "02_changes_requested", ...). Probing the
# selection and keeping the literals only as a fallback means a renamed or
# added state does not silently reclassify everybody's work list.
CLOSED_STATE_FALLBACK = ("1_done", "1_canceled")

# Stage names are matched lower-cased, never by id: each project owns its own
# project.task.type records, so there is no shared id to hardcode. This mirrors
# c2p_project_tracker._stage_name().
WAITING_STAGE_HINTS = ("waiting on client", "waiting for client", "waiting")
REVIEW_STAGE_HINTS = ("review", "in review", "for review", "qa")


class ProjectTask(models.Model):
    _inherit = "project.task"

    # The freshness signal the update policy in the directive needs. Nothing in
    # the existing estate records "when did this task last get a real update" —
    # write_date moves for any field change, including bulk edits, so it cannot
    # answer the question.
    c2p_last_update = fields.Datetime(
        string="Last Progress Update", readonly=True, copy=False, index=True,
        help="Set only by a deliberate progress update, never by an incidental "
             "write. This is what staleness is measured against.")
    c2p_next_action = fields.Char(
        string="Next Action", copy=False,
        help="The one thing that happens next on this task.")

    # ── helpers ─────────────────────────────────────────────────────────
    @api.model
    def _c2p_closed_states(self):
        """Values of `state` that mean the task needs no further work."""
        try:
            keys = [k for k, _label in self._fields["state"].selection]
        except Exception:
            return list(CLOSED_STATE_FALLBACK)
        closed = [k for k in keys if k.startswith("1_")]
        return closed or list(CLOSED_STATE_FALLBACK)

    def _c2p_stage_name(self):
        self.ensure_one()
        return (self.stage_id.name or "").strip().lower()

    def _c2p_is_waiting_stage(self):
        name = self._c2p_stage_name()
        return any(h in name for h in WAITING_STAGE_HINTS)

    def _c2p_is_review_stage(self):
        name = self._c2p_stage_name()
        return any(h in name for h in REVIEW_STAGE_HINTS)

    @api.model
    def _c2p_blocker_field(self):
        """`blocked_reason` when c2p_project_tracker is installed, else None.

        Declaring a second blocker field would give the business two answers to
        one question, so the hub reuses the tracker's field when it exists and
        degrades to chatter-only when it does not.
        """
        return "blocked_reason" if "blocked_reason" in self._fields else None

    def _c2p_find_stage(self, hints):
        """A stage of this task's project whose name matches one of `hints`."""
        self.ensure_one()
        if not self.project_id:
            return self.env["project.task.type"].browse()
        stages = self.env["project.task.type"].search(
            [("project_ids", "in", self.project_id.ids)], order="sequence, id")
        for hint in hints:
            for stage in stages:
                if hint in (stage.name or "").strip().lower():
                    return stage
        return self.env["project.task.type"].browse()

    # ── the fifteen-second update ───────────────────────────────────────
    def action_c2p_quick_update(self, payload=None):
        """Record a progress update in one call.

        `payload` keys, all optional:
          progress      str  what happened; posted to chatter
          next_action   str  the one next step
          blocker       str  what is blocking; also moves the task to a
                             waiting stage when the project has one
          state         str  a project.task.state value to move to
          clear_blocker bool unblock and return to the previous flow

        Everything goes through write(), so c2p_project_tracker's waiting_since
        bookkeeping, baseline capture and portfolio resync all keep working. The
        blocker is collected in the same call because that module's
        _check_blocked_reason refuses a Waiting-on-Client stage without one —
        asking for it afterwards would just raise at the user.
        """
        self.ensure_one()
        payload = payload or {}
        progress = (payload.get("progress") or "").strip()
        next_action = (payload.get("next_action") or "").strip()
        blocker = (payload.get("blocker") or "").strip()
        new_state = payload.get("state") or False
        clear_blocker = bool(payload.get("clear_blocker"))

        if not any([progress, next_action, blocker, new_state, clear_blocker]):
            raise UserError(_("Nothing to update. Add progress, a next action, "
                              "a blocker or a new status."))

        vals = {"c2p_last_update": fields.Datetime.now()}
        if next_action or clear_blocker:
            vals["c2p_next_action"] = next_action or False

        blocker_field = self._c2p_blocker_field()
        if blocker and blocker_field:
            vals[blocker_field] = blocker
        elif clear_blocker and blocker_field:
            vals[blocker_field] = False

        if new_state:
            valid = [k for k, _l in self._fields["state"].selection]
            if new_state not in valid:
                raise UserError(_("Unknown status %s.", new_state))
            vals["state"] = new_state

        # A blocker moves the task to the project's waiting stage when it has
        # one. Without a matching stage the blocker is still recorded — the
        # update must never be lost because a project is configured differently.
        if blocker and not self._c2p_is_waiting_stage():
            stage = self._c2p_find_stage(WAITING_STAGE_HINTS)
            if stage:
                vals["stage_id"] = stage.id

        self.write(vals)

        body = self._c2p_update_body(progress, next_action, blocker, clear_blocker)
        if body:
            self.message_post(body=body, subtype_xmlid="mail.mt_note")
        return True

    def _c2p_update_body(self, progress, next_action, blocker, clear_blocker):
        """The chatter entry. Plain, scannable, and it says who and what.

        The three text values come straight from a user, so they are escaped
        rather than interpolated: `Markup(...) % value` escapes the operand
        while keeping the surrounding tags live. Building this body with plain
        %-formatting would store whatever markup the user typed.
        """
        parts = []
        if progress:
            parts.append(Markup("<p><b>%s</b> %s</p>") % (_("Progress:"), progress))
        if blocker:
            parts.append(Markup("<p><b>%s</b> %s</p>") % (_("Blocked:"), blocker))
        if clear_blocker:
            parts.append(Markup("<p><b>%s</b></p>") % _("Unblocked."))
        if next_action:
            parts.append(Markup("<p><b>%s</b> %s</p>") % (_("Next:"), next_action))
        return Markup("").join(parts)

    def action_c2p_submit_for_review(self):
        """Move to the project's review stage, or say why it cannot."""
        self.ensure_one()
        stage = self._c2p_find_stage(REVIEW_STAGE_HINTS)
        if not stage:
            raise UserError(_(
                "Project %s has no review stage, so there is nowhere to submit "
                "this task to. Add one, or move the task by hand.",
                self.project_id.display_name or _("(none)")))
        self.write({"stage_id": stage.id,
                    "c2p_last_update": fields.Datetime.now()})
        self.message_post(body=Markup("<p>%s</p>") % _("Submitted for review."),
                          subtype_xmlid="mail.mt_note")
        return True
