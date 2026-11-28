import contextvars
from contextlib import contextmanager

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# One limit for every project, by decision (25 Nov 2026). Calendar days,
# because commitments are dates.
AMBER_MAX_DAYS = 5

HEALTH = [
    ("green", "Green"),
    ("amber", "Amber"),
    ("red", "Red"),
    ("grey", "No forecast"),
]

# Switches for trusted code in this process. They are not context keys: a
# context is chosen by whoever calls the API, so a key in it can be sent by
# anyone with a login. These variables can only be set by Python code that
# imports this module.
_INTERNAL = contextvars.ContextVar("c2p_forecast_internal", default=False)
_SKIP_REASON = contextvars.ContextVar("c2p_forecast_skip_reason", default=False)


@contextmanager
def _switched_on(var):
    token = var.set(True)
    try:
        yield
    finally:
        var.reset(token)


def skip_change_reason():
    """For trusted bulk code: `with skip_change_reason(): milestone.write(...)`.

    The reason rule is off inside the block only.
    """
    return _switched_on(_SKIP_REASON)


def health_for(commitment, forecast):
    """The colour for one milestone. Pure, so the boundaries are testable."""
    if not forecast:
        return "grey"
    if not commitment:
        # A forecast with nothing to measure it against is not "on time".
        return "grey"
    late = (forecast - commitment).days
    if late <= 0:
        return "green"
    if late <= AMBER_MAX_DAYS:
        return "amber"
    return "red"


class ProjectMilestone(models.Model):
    _inherit = "project.milestone"

    c2p_forecast_date = fields.Date(
        string="Forecast Date", tracking=True, copy=False,
        help="When the delivery owner now expects this milestone. The "
             "Deadline is the commitment date and does not move with it.")
    c2p_health = fields.Selection(
        HEALTH, string="Health", default="grey", required=True, readonly=True,
        copy=False, index=True,
        help="Calculated from the forecast and the commitment date. A reached "
             "milestone keeps the colour it had when it was reached.")
    c2p_days_late = fields.Integer(
        string="Days Late", compute="_compute_c2p_days_late",
        help="Calendar days the forecast is after the commitment date.")
    # Not stored: it travels with one save, goes into that save's history
    # entry, and is gone.
    c2p_change_reason = fields.Char(
        string="Reason for Change", store=False,
        help="Required when a commitment date or a forecast date is changed.")

    @api.depends("deadline", "c2p_forecast_date")
    def _compute_c2p_days_late(self):
        for ms in self:
            if ms.deadline and ms.c2p_forecast_date:
                ms.c2p_days_late = max(
                    0, (ms.c2p_forecast_date - ms.deadline).days)
            else:
                ms.c2p_days_late = 0

    @api.onchange("deadline", "c2p_forecast_date")
    def _onchange_c2p_preview_health(self):
        """Show the colour the dates being typed will give, before saving.

        Display only: the field is read-only, so the form never sends it, and
        the stored value is still set by the save itself.
        """
        if not self.is_reached:
            self.c2p_health = health_for(self.deadline, self.c2p_forecast_date)

    # ── health is calculated, never typed ────────────────────────────────
    def _c2p_refresh_health(self):
        """Recalculate the colour of milestones that are not reached.

        A reached milestone is skipped on purpose: it keeps the colour it had
        when it was reached.
        """
        for ms in self:
            if ms.is_reached:
                continue
            colour = health_for(ms.deadline, ms.c2p_forecast_date)
            if ms.c2p_health != colour:
                ms._c2p_store_health(colour)

    def _c2p_store_health(self, colour):
        """The one place the stored colour is written."""
        with _switched_on(_INTERNAL):
            super(ProjectMilestone, self).write({"c2p_health": colour})

    def _c2p_reason_exempt(self):
        # System writes (the superuser, which also runs the install) and code
        # inside `skip_change_reason()`. No context key counts.
        return bool(self.env.su or _SKIP_REASON.get())

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.pop("c2p_change_reason", None)
            if not _INTERNAL.get():
                vals.pop("c2p_health", None)
        milestones = super().create(vals_list)
        for ms in milestones:
            # Created already reached: take the colour of its dates once.
            colour = health_for(ms.deadline, ms.c2p_forecast_date)
            if ms.c2p_health != colour:
                ms._c2p_store_health(colour)
        return milestones

    def write(self, vals):
        if _INTERNAL.get():
            return super().write(vals)
        vals = dict(vals)
        if "c2p_health" in vals:
            raise UserError(_(
                "Milestone health is calculated from the forecast and the "
                "commitment date. It cannot be set by hand."))
        reason = (vals.pop("c2p_change_reason", None) or "").strip()

        watched = [f for f in ("deadline", "c2p_forecast_date") if f in vals]
        changed = self.browse()
        if watched:
            for ms in self:
                for fname in watched:
                    old = ms[fname]
                    new = fields.Date.to_date(vals[fname]) if vals[fname] else False
                    # Entering a date for the first time is planning, not a
                    # change. Moving or clearing an existing one is.
                    if old and new != old:
                        changed |= ms
            if changed and not reason and not self._c2p_reason_exempt():
                raise UserError(_(
                    "Enter a Reason for Change before saving: the commitment "
                    "date or the forecast date of '%s' is being changed.",
                    changed[0].name))
            if changed and reason:
                # Same history entry as the tracked old -> new values.
                changed._track_set_log_message(
                    Markup("<p><b>%s</b> %s</p>") % (
                        _("Reason for change:"), reason))

        # Reaching a milestone freezes its colour as of this save, so refresh
        # with the new dates first and only then let it become reached.
        becoming_reached = self.browse()
        if vals.get("is_reached"):
            becoming_reached = self.filtered(lambda m: not m.is_reached)
        res = super().write(vals)
        for ms in becoming_reached:
            colour = health_for(ms.deadline, ms.c2p_forecast_date)
            if ms.c2p_health != colour:
                ms._c2p_store_health(colour)
        if {"deadline", "c2p_forecast_date", "is_reached"} & set(vals):
            (self - becoming_reached)._c2p_refresh_health()
        return res
