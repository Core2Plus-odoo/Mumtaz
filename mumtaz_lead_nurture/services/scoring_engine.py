"""
Scoring Engine
==============
Applies qualification score changes to a CRM lead based on named events.
Rules are stored in lead.nurture.rule and looked up dynamically.
"""

import logging

_logger = logging.getLogger(__name__)

# Default score deltas used if no DB rules exist (bootstrap fallback)
DEFAULT_SCORES = {
    "lead_enrolled": 5,
    "email_sent": 3,
    "email_opened": 5,
    "email_clicked": 8,
    "whatsapp_sent": 3,
    "reply_received": 15,
    "positive_reply": 20,
    "demo_requested": 30,
    "requirement_shared": 25,
    "manual_qualified": 40,
    "not_interested": -20,
    "bounced": -5,
}


class ScoringEngine:
    def __init__(self, env):
        self.env = env

    def apply_event(self, lead, event_name):
        """
        Look up scoring rules for event_name, apply total delta to lead.
        Updates qualification_score, nurture_stage, and auto_convert_ready.
        Returns the score delta applied.
        """
        rules = self.env["lead.nurture.rule"].search(
            [("trigger_event", "=", event_name), ("active", "=", True)]
        )

        if rules:
            delta = sum(r.score_change for r in rules)
        else:
            delta = DEFAULT_SCORES.get(event_name, 0)

        if delta == 0:
            return 0

        new_score = max(0, lead.qualification_score + delta)
        vals = {"qualification_score": new_score}

        campaign = lead.nurture_campaign_id
        if campaign:
            if new_score >= campaign.auto_convert_threshold and not lead.auto_convert_ready:
                vals["auto_convert_ready"] = True
                _logger.info(
                    "Lead %s reached auto-convert threshold (%d)", lead.id, campaign.auto_convert_threshold
                )
            elif (
                new_score >= campaign.qualification_threshold
                and lead.nurture_stage not in ("qualified", "converted", "dead")
            ):
                vals["nurture_stage"] = "qualified"

        lead.write(vals)
        _logger.debug(
            "Scoring [%s] lead=%s delta=%+d new_score=%d", event_name, lead.id, delta, new_score
        )
        return delta
