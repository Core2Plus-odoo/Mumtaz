"""The proposal-stage flag the follow-up agent selects on."""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

# Substrings that identify a proposal stage on a pipeline nobody has flagged
# yet. Used once, at install, to seed the checkbox — never at runtime.
PROPOSAL_STAGE_HINTS = ("propos", "quot", "offer")


class CrmStage(models.Model):
    _inherit = "crm.stage"

    is_proposal_stage = fields.Boolean(
        string="Proposal Stage",
        help="The Proposal Follow-up agent chases opportunities that have sat "
        "in a stage flagged here for too long. Tick it on every stage that "
        "means a proposal is out with the client.",
    )


def seed_proposal_stages(env):
    """Tick the flag on stages that already read as proposal stages.

    Runs once, from the install hook. Matching on names at *runtime* would be
    the fragile thing — rename "Proposal" to "Proposal Sent" in Arabic and the
    agent silently stops selecting anything. Matching once to set a checkbox
    that a human can then see and correct is the readable version of the same
    idea.
    """
    stages = env["crm.stage"].search([("is_proposal_stage", "=", False)])
    matched = stages.filtered(
        lambda stage: any(
            hint in (stage.name or "").lower() for hint in PROPOSAL_STAGE_HINTS
        )
    )
    if matched:
        matched.is_proposal_stage = True
        _logger.info(
            "c2p_agents: flagged %s as proposal stage(s): %s",
            len(matched),
            ", ".join(matched.mapped("name")),
        )
    else:
        _logger.warning(
            "c2p_agents: no CRM stage looked like a proposal stage, so the "
            "Proposal Follow-up agent will select nothing until one is ticked "
            "under CRM > Configuration > Stages."
        )
