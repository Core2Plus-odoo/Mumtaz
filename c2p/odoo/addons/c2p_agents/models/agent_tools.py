"""The four helpers the agents share.

Plain module-level functions taking ``env``, not an abstract model mixed into
the registry. There are four of them, none holds state, and this way a reader
can follow what an agent does without first knowing how Odoo composes
``_inherit`` chains.
"""

import logging

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DRY_RUN_PARAM = "c2p_agents.dry_run"

# Values that mean "off". Anything else — including a typo — reads as on,
# because the parameter is `dry_run` and a typo should leave the agents safe
# rather than arm them against live client data.
FALSEY = {"false", "0", "no", "off", ""}


def dry_run_enabled(env, explicit=None):
    """Resolve dry-run: an explicit argument wins, otherwise the parameter."""
    if explicit is not None:
        return bool(explicit)
    # sudo: the agents run under whichever user owns the cron, which is not
    # guaranteed to hold Settings access. This is module configuration, not
    # customer data.
    value = env["ir.config_parameter"].sudo().get_param(DRY_RUN_PARAM, "True")
    return str(value).strip().lower() not in FALSEY


def activity_type(env, xml_id):
    """Resolve an activity type by XML ID, loudly.

    Raising stops the run and Odoo flags the cron as failed. The alternative —
    skipping quietly — is exactly how the old server actions reported success
    every night while doing nothing.
    """
    found = env.ref(xml_id, raise_if_not_found=False)
    if not found:
        raise UserError(
            _(
                "C2P Agents: the activity type %s is missing from this database, "
                "so the agent cannot schedule anything.",
                xml_id,
            )
        )
    return found


def already_flagged(env, res_model, res_ids, activity_type_id, summary):
    """Return the subset of ``res_ids`` already carrying this agent's activity.

    One query for the whole batch, not one per record. It reads every user's
    activities: one assigned to a colleague still means the record has been
    flagged, and missing it would create a duplicate.
    """
    if not res_ids:
        return set()
    # sudo: see above — the check is only correct if it can see activities
    # belonging to users other than the one running the cron.
    rows = env["mail.activity"].sudo().search_read(
        [
            ("res_model", "=", res_model),
            ("res_id", "in", list(res_ids)),
            ("activity_type_id", "=", activity_type_id),
            ("summary", "=", summary),
        ],
        ["res_id"],
    )
    return {row["res_id"] for row in rows}


def log_run(env, agent, scanned, acted, dry_run, limit, note=""):
    """Record what a run did — always, including when it did nothing.

    A crash needs no help from here: Odoo marks the cron failed and logs the
    traceback. What this catches is the quiet failure, the run that completes
    and touches nothing, which is what went unnoticed before.
    """
    detail = "scanned=%s acted=%s limit=%s%s%s" % (
        scanned,
        acted,
        limit,
        " (dry run — nothing written)" if dry_run else "",
        " — %s" % note if note else "",
    )
    _logger.info("C2P Agents [%s] %s", agent, detail)
    # sudo: the run log is an audit trail and must be written whatever rights
    # the cron user happens to hold.
    env["c2p.agent.run"].sudo().create(
        {
            "agent": agent,
            "scanned": scanned,
            "acted": acted,
            "dry_run": dry_run,
            "limit_applied": limit,
            "note": detail,
        }
    )
    return {
        "agent": agent,
        "scanned": scanned,
        "acted": acted,
        "dry_run": dry_run,
        "limit": limit,
    }
