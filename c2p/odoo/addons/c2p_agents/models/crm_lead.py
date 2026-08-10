"""Agents 1-3: lead scoring, stale opportunities, proposal follow-up.

The scoring weights below are the one part of this module that is a placeholder.
They are written as plain module-level constants precisely so that reconciling
them against the original server-action code is a diff of a table, not a rewrite
of a method.
"""

from datetime import timedelta

from odoo import api, fields, models

# --------------------------------------------------------------------------
# Scoring weights — PLACEHOLDER, pending the original server-action code.
# --------------------------------------------------------------------------

# Matched case-insensitively against the UTM source name, so renaming a source
# in the UI changes scoring visibly rather than by silent lookup failure.
SOURCE_SCORES = {
    "referral": 25,
    "website": 15,
    "search engine": 12,
    "linkedin": 12,
    "email campaign": 8,
    "newsletter": 5,
    "facebook": 5,
    "cold list": 0,
}

# ISO country codes, resolved through res.country.code — no database IDs.
COUNTRY_SCORES = {
    "AE": 25,
    "SA": 20,
    "QA": 15,
    "KW": 15,
    "OM": 12,
    "BH": 12,
    "PK": 8,
}

# An address at one of these is a person, not a business.
FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "gmx.com",
        "yandex.com",
        "mail.ru",
        "rediffmail.com",
    }
)

SCORE_BUSINESS_EMAIL = 15
SCORE_PHONE = 10
SCORE_NAMED_CONTACT = 10

# (expected revenue at or above, points). First match wins, so keep descending.
REVENUE_BANDS = ((100000, 25), (50000, 20), (20000, 12), (5000, 6))

# (total score at or above, crm.lead priority). First match wins.
PRIORITY_BANDS = ((60, "3"), (40, "2"), (20, "1"))
PRIORITY_FLOOR = "0"

# --------------------------------------------------------------------------
# Agent constants
# --------------------------------------------------------------------------

# Priorities the stale-opportunity agent considers worth chasing.
HIGH_PRIORITIES = ("2", "3")

# The activity summary doubles as this module's duplicate marker: an open
# activity carrying this exact text means the record has already been flagged.
# Changing one of these strings makes every already-flagged record eligible
# again on the next run, so treat them as data, not copy.
STALE_SUMMARY = "C2P Agent: stale opportunity"
PROPOSAL_SUMMARY = "C2P Agent: proposal follow-up"


class CrmLead(models.Model):
    _name = "crm.lead"
    _inherit = ["crm.lead", "c2p.agent.mixin"]

    # ------------------------------------------------------------------
    # Agent 1 — lead scoring
    # ------------------------------------------------------------------
    def _c2p_email_domain(self):
        """The domain part of ``email_from``, tolerating "Name <a@b.com>"."""
        self.ensure_one()
        email = (self.email_from or "").strip().lower()
        if "<" in email and ">" in email:
            email = email[email.rfind("<") + 1 : email.rfind(">")]
        return email.rpartition("@")[2].strip()

    def _c2p_has_phone(self):
        self.ensure_one()
        # `mobile` has come and gone from crm.lead across recent versions, so it
        # is read defensively rather than assumed present on v19.
        mobile = self.mobile if "mobile" in self._fields else False
        return bool(self.phone or mobile)

    def _c2p_lead_score(self):
        """Total the scoring rules for one lead. No side effects."""
        self.ensure_one()
        score = 0

        if self.source_id:
            score += SOURCE_SCORES.get((self.source_id.name or "").strip().lower(), 0)

        if self.country_id:
            score += COUNTRY_SCORES.get(self.country_id.code, 0)

        domain = self._c2p_email_domain()
        if domain and domain not in FREE_EMAIL_DOMAINS:
            score += SCORE_BUSINESS_EMAIL

        for threshold, points in REVENUE_BANDS:
            if (self.expected_revenue or 0) >= threshold:
                score += points
                break

        if self._c2p_has_phone():
            score += SCORE_PHONE

        if self.contact_name or self.partner_id:
            score += SCORE_NAMED_CONTACT

        return score

    def _c2p_lead_priority(self):
        """Map a lead's score onto a ``crm.lead`` priority."""
        self.ensure_one()
        score = self._c2p_lead_score()
        for threshold, priority in PRIORITY_BANDS:
            if score >= threshold:
                return priority
        return PRIORITY_FLOOR

    @api.model
    def _c2p_lead_scoring_domain(self):
        return [("active", "=", True)]

    @api.model
    def _cron_score_leads(self, limit=None, dry_run=None):
        """Set priority on ``crm.lead`` from the scoring rules.

        Ordered by ``write_date desc`` so that under a limit the agent always
        rescores whatever moved most recently, which is the behaviour a nightly
        job wants: a record nobody has touched does not need rescoring.
        """
        limit = limit or self._c2p_param_int("lead_scoring_limit", 200)
        dry_run = self._c2p_dry_run(dry_run)
        scanned = acted = 0
        try:
            leads = self.search(
                self._c2p_lead_scoring_domain(), limit=limit, order="write_date desc"
            )
            scanned = len(leads)
            for lead in leads:
                priority = lead._c2p_lead_priority()
                if priority == lead.priority:
                    continue
                acted += 1
                if not dry_run:
                    lead.priority = priority
        except Exception:
            self._c2p_log_failure("lead_scoring", scanned, acted, dry_run, limit)
            raise
        return self._c2p_finish("lead_scoring", scanned, acted, dry_run, limit)

    # ------------------------------------------------------------------
    # Agent 2 — stale opportunity detection
    # ------------------------------------------------------------------
    @api.model
    def _c2p_stale_domain(self, cutoff):
        return [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("priority", "in", list(HIGH_PRIORITIES)),
            # Won opportunities are at 100; lost ones are archived, so `active`
            # already excludes them.
            ("probability", "<", 100),
            ("activity_ids", "=", False),
            ("write_date", "<=", cutoff),
        ]

    @api.model
    def _cron_flag_stale_opportunities(self, limit=None, dry_run=None):
        """Raise a To-Do on high-priority opportunities that have gone quiet."""
        limit = limit or self._c2p_param_int("stale_limit", 50)
        days = self._c2p_param_int("stale_days", 21)
        dry_run = self._c2p_dry_run(dry_run)
        scanned = acted = 0
        try:
            activity_type = self._c2p_activity_type("mail.mail_activity_data_todo")
            cutoff = fields.Datetime.now() - timedelta(days=days)
            leads = self.search(
                self._c2p_stale_domain(cutoff), limit=limit, order="write_date asc"
            )
            scanned = len(leads)
            flagged = self._c2p_already_flagged(
                "crm.lead", leads.ids, activity_type, STALE_SUMMARY
            )
            deadline = fields.Date.context_today(self)
            for lead in leads:
                if lead.id in flagged:
                    continue
                acted += 1
                if dry_run:
                    continue
                lead._c2p_schedule_activity(
                    activity_type,
                    STALE_SUMMARY,
                    _stale_note(lead, days),
                    lead.user_id or self.env.user,
                    deadline,
                )
        except Exception:
            self._c2p_log_failure("stale_opportunity", scanned, acted, dry_run, limit)
            raise
        return self._c2p_finish("stale_opportunity", scanned, acted, dry_run, limit)

    # ------------------------------------------------------------------
    # Agent 3 — proposal follow-up
    # ------------------------------------------------------------------
    @api.model
    def _c2p_proposal_domain(self, cutoff):
        return [
            ("active", "=", True),
            ("stage_id.is_proposal_stage", "=", True),
            ("probability", "<", 100),
            ("activity_ids", "=", False),
            ("date_last_stage_update", "<=", cutoff),
        ]

    @api.model
    def _cron_followup_proposals(self, limit=None, dry_run=None):
        """Raise a Call on leads parked in a proposal stage.

        Selects on ``date_last_stage_update`` — time in *this* stage — rather
        than ``write_date``, so editing an unrelated field does not reset the
        clock on a proposal nobody has chased.
        """
        limit = limit or self._c2p_param_int("proposal_limit", 50)
        days = self._c2p_param_int("proposal_days", 7)
        dry_run = self._c2p_dry_run(dry_run)
        scanned = acted = 0
        try:
            activity_type = self._c2p_activity_type("mail.mail_activity_data_call")
            cutoff = fields.Datetime.now() - timedelta(days=days)
            leads = self.search(
                self._c2p_proposal_domain(cutoff),
                limit=limit,
                order="date_last_stage_update asc",
            )
            scanned = len(leads)
            flagged = self._c2p_already_flagged(
                "crm.lead", leads.ids, activity_type, PROPOSAL_SUMMARY
            )
            deadline = fields.Date.context_today(self)
            for lead in leads:
                if lead.id in flagged:
                    continue
                acted += 1
                if dry_run:
                    continue
                lead._c2p_schedule_activity(
                    activity_type,
                    PROPOSAL_SUMMARY,
                    _proposal_note(lead, days),
                    lead.user_id or self.env.user,
                    deadline,
                )
        except Exception:
            self._c2p_log_failure("proposal_followup", scanned, acted, dry_run, limit)
            raise
        return self._c2p_finish("proposal_followup", scanned, acted, dry_run, limit)


def _stale_note(lead, days):
    return (
        "No activity on this opportunity for %s days or more. "
        "Expected revenue: %s. Raised automatically by the C2P stale "
        "opportunity agent." % (days, lead.expected_revenue or 0)
    )


def _proposal_note(lead, days):
    return (
        "This opportunity has been in %s for %s days or more with no activity "
        "scheduled. Raised automatically by the C2P proposal follow-up agent."
        % (lead.stage_id.name or "a proposal stage", days)
    )
