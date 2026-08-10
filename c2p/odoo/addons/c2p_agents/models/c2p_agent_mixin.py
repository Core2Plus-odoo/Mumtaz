"""Shared plumbing for the four nightly agents.

Deliberately small. It holds only the three things all four agents need and
would otherwise each get subtly wrong: reading settings, deciding whether this
is a dry run, and creating an activity without creating it twice.
"""

import logging
import traceback

from odoo import _, SUPERUSER_ID, api, models, registry
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_PREFIX = "c2p_agents."

# Values that mean "off" in an ir.config_parameter. Anything else — including a
# typo — reads as on, because the parameter being read is `dry_run` and a typo
# should leave the agents safe rather than arm them.
FALSEY = {"false", "0", "no", "off", ""}


class C2pAgentMixin(models.AbstractModel):
    _name = "c2p.agent.mixin"
    _description = "C2P Agent Mixin"

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    @api.model
    def _c2p_param(self, key, default=None):
        """Read one ``c2p_agents.*`` system parameter."""
        # sudo: the agents run under whichever user owns the cron, which is not
        # guaranteed to hold Settings access. These parameters are module
        # configuration, not customer data.
        value = self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + key)
        return default if value in (None, False, "") else value

    @api.model
    def _c2p_param_int(self, key, default):
        try:
            return int(str(self._c2p_param(key, default)).strip())
        except (TypeError, ValueError):
            _logger.warning(
                "C2P Agents: system parameter %s%s is not a whole number, "
                "falling back to %s",
                PARAM_PREFIX,
                key,
                default,
            )
            return default

    @api.model
    def _c2p_dry_run(self, dry_run=None):
        """Resolve dry-run: an explicit argument wins, otherwise the parameter.

        Defaults to ``True`` in every direction that could go wrong — a missing
        parameter, an unreadable one, an unrecognised value. Arming the agents
        against live client data should take a deliberate act.
        """
        if dry_run is not None:
            return bool(dry_run)
        return str(self._c2p_param("dry_run", "True")).strip().lower() not in FALSEY

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------
    @api.model
    def _c2p_activity_type(self, xml_id):
        """Resolve an activity type by XML ID, loudly.

        Raising here stops the run and records the failure. The alternative —
        skipping quietly — is precisely how the server actions managed to report
        success every night while doing nothing.
        """
        activity_type = self.env.ref(xml_id, raise_if_not_found=False)
        if not activity_type:
            raise UserError(
                _(
                    "C2P Agents: the activity type %s is missing from this "
                    "database, so the agent cannot schedule anything.",
                    xml_id,
                )
            )
        return activity_type

    @api.model
    def _c2p_already_flagged(self, res_model, res_ids, activity_type, summary):
        """Return the subset of ``res_ids`` that already carry this agent's activity.

        One query for the whole batch rather than one per record, and it reads
        every user's activities: an activity assigned to a colleague still means
        the record has been flagged, and missing it would create a duplicate.
        """
        if not res_ids:
            return set()
        # sudo: see above — the duplicate check is only correct if it can see
        # activities belonging to users other than the one running the cron.
        rows = self.env["mail.activity"].sudo().search_read(
            [
                ("res_model", "=", res_model),
                ("res_id", "in", list(res_ids)),
                ("activity_type_id", "=", activity_type.id),
                ("summary", "=", summary),
            ],
            ["res_id"],
        )
        return {row["res_id"] for row in rows}

    def _c2p_schedule_activity(self, activity_type, summary, note, user, deadline):
        """Schedule one activity on ``self`` through the standard mixin helper."""
        self.ensure_one()
        self.activity_schedule(
            activity_type_id=activity_type.id,
            summary=summary,
            note=note,
            user_id=user.id,
            date_deadline=deadline,
        )

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------
    @api.model
    def _c2p_log_run(
        self, agent, scanned, acted, dry_run, limit_applied, note=False, error=False
    ):
        """Record what a run did. Always — including when it did nothing."""
        # sudo: the run log is an audit trail. It has to be written whatever
        # rights the cron user happens to hold, or the first thing lost in a
        # permissions change is the evidence that the agents stopped working.
        return self.env["c2p.agent.run"].sudo().create(
            {
                "agent": agent,
                "scanned": scanned,
                "acted": acted,
                "dry_run": dry_run,
                "limit_applied": limit_applied,
                "note": note,
                "error": error,
            }
        )

    @api.model
    def _c2p_log_failure(self, agent, scanned, acted, dry_run, limit_applied):
        """Record a failed run on a cursor of its own. Call from inside `except`.

        The agents re-raise, so the cron runner rolls the transaction back — and
        an ordinary log row would go back with it, leaving no trace of exactly
        the run that needed one. A separate cursor commits independently of that
        rollback.

        Never raises. If this fails too, the original exception is the one worth
        propagating, so the failure to log is written to the server log instead.
        """
        detail = traceback.format_exc()
        try:
            with registry(self.env.cr.dbname).cursor() as cr:
                api.Environment(cr, SUPERUSER_ID, {})["c2p.agent.run"].create(
                    {
                        "agent": agent,
                        "scanned": scanned,
                        "acted": acted,
                        "dry_run": dry_run,
                        "limit_applied": limit_applied,
                        "note": "failed after scanning %s and acting on %s"
                        % (scanned, acted),
                        "error": detail,
                    }
                )
        except Exception:
            _logger.exception(
                "C2P Agents [%s] failed, and the failure could not be recorded",
                agent,
            )

    @api.model
    def _c2p_finish(self, agent, scanned, acted, dry_run, limit):
        """Close out a successful run: log it, record it, return the summary."""
        note = "scanned=%s acted=%s limit=%s%s" % (
            scanned,
            acted,
            limit,
            " (dry run — nothing written)" if dry_run else "",
        )
        _logger.info("C2P Agents [%s] %s", agent, note)
        self._c2p_log_run(agent, scanned, acted, dry_run, limit, note=note)
        return {
            "agent": agent,
            "scanned": scanned,
            "acted": acted,
            "dry_run": dry_run,
            "limit": limit,
        }
