"""Agents 1-3: lead scoring, stale opportunities, proposal follow-up.

Thresholds live here as constants rather than in ``ir.config_parameter``. A
value that governs behaviour belongs next to the code it governs, where it can
be diffed and reviewed — putting it in a database field is the same habit that
produced the empty server actions. ``dry_run`` is the one exception: flipping it
is an operational act, not a code change.

The scoring weights are the one part of this module that is a placeholder. They
are plain module-level tables so that reconciling them against the intended
rules is a diff of a table, not a rewrite of a method.
"""

from datetime import timedelta

from odoo import api, fields, models

from .agent_tools import activity_type, already_flagged, dry_run_enabled, log_run
from .email_validation import (
    FREE_EMAIL_DOMAINS,
    INVALID,
    RISKY,
    VALID,
    address_domain,
    validate_address,
)

# --------------------------------------------------------------------------
# Scoring weights — PLACEHOLDER, pending the original rules.
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

SCORE_BUSINESS_EMAIL = 15
SCORE_PHONE = 10
SCORE_NAMED_CONTACT = 10

# (expected revenue at or above, points). First match wins, so keep descending.
REVENUE_BANDS = ((100000, 25), (50000, 20), (20000, 12), (5000, 6))

# (total score at or above, crm.lead priority). First match wins.
PRIORITY_BANDS = ((60, "3"), (40, "2"), (20, "1"))
PRIORITY_FLOOR = "0"

# --------------------------------------------------------------------------
# Agent settings
# --------------------------------------------------------------------------

LEAD_SCORING_LIMIT = 200

# Days of silence before a high-priority opportunity counts as stale.
STALE_DAYS = 21
STALE_LIMIT = 50

# Days parked in a proposal stage before the opportunity gets chased.
PROPOSAL_DAYS = 7
PROPOSAL_LIMIT = 50

# Substrings that identify a proposal stage. Matched at run time against stage
# names — see _c2p_proposal_stage_ids for the trade-off that represents.
PROPOSAL_STAGE_HINTS = ("propos", "quot", "offer")

EMAIL_VALIDATION_LIMIT = 100

# Priorities the stale-opportunity agent considers worth chasing.
HIGH_PRIORITIES = ("2", "3")

# The activity summary doubles as the duplicate marker: an open activity
# carrying this exact text means the record has already been flagged. Changing
# one makes every already-flagged record eligible again, so treat them as data.
STALE_SUMMARY = "C2P Agent: stale opportunity"
PROPOSAL_SUMMARY = "C2P Agent: proposal follow-up"


class CrmLead(models.Model):
    _inherit = "crm.lead"

    c2p_email_validity = fields.Selection(
        [
            ("unknown", "Not checked"),
            (VALID, "Valid"),
            (RISKY, "Risky"),
            (INVALID, "Invalid"),
        ],
        default="unknown",
        index=True,
        copy=False,
        help="Set by the email validation agent. Risky means deliverable but "
        "a consumer mailbox; invalid means do not send.",
    )
    c2p_email_validity_detail = fields.Char(readonly=True, copy=False)
    c2p_email_checked_on = fields.Datetime(readonly=True, copy=False)
    c2p_outreach_channel = fields.Selection(
        [
            ("email", "Email"),
            ("whatsapp", "WhatsApp"),
            ("none", "No usable channel"),
        ],
        compute="_compute_c2p_outreach_channel",
        store=True,
        help="Where outreach should go. Falls back to WhatsApp when the email "
        "address is unusable and a number is on file.",
    )

    @api.depends("c2p_email_validity", "email_from", "phone")
    def _compute_c2p_outreach_channel(self):
        """Route outreach: email unless it is unusable, then the number.

        Stored so it can be filtered and grouped — picking a send list is the
        whole point, and a non-stored field could not be searched.

        `mobile` is deliberately absent from the depends: the field has come and
        gone from crm.lead across versions, and naming a field that does not
        exist fails the registry at install. Editing only the mobile number
        therefore leaves this stale until something else on the lead changes.
        """
        for lead in self:
            usable_email = lead.email_from and lead.c2p_email_validity != INVALID
            if usable_email:
                lead.c2p_outreach_channel = "email"
            elif lead._c2p_has_phone():
                lead.c2p_outreach_channel = "whatsapp"
            else:
                lead.c2p_outreach_channel = "none"

    # ------------------------------------------------------------------
    # Agent 1 — lead scoring
    # ------------------------------------------------------------------
    def _c2p_email_domain(self):
        """The domain part of ``email_from``, tolerating "Name <a@b.com>"."""
        self.ensure_one()
        return address_domain(self.email_from)

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
    def _cron_score_leads(self, limit=LEAD_SCORING_LIMIT, dry_run=None):
        """Set priority on ``crm.lead`` from the scoring rules.

        Ordered by ``write_date desc`` so that under a limit the agent rescores
        whatever moved most recently — a record nobody has touched does not need
        rescoring.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        leads = self.search([("active", "=", True)], limit=limit, order="write_date desc")
        acted = 0
        for lead in leads:
            priority = lead._c2p_lead_priority()
            if priority == lead.priority:
                continue
            acted += 1
            if not dry_run:
                lead.priority = priority
        return log_run(self.env, "lead_scoring", len(leads), acted, dry_run, limit)

    # ------------------------------------------------------------------
    # Agent 2 — stale opportunity detection
    # ------------------------------------------------------------------
    @api.model
    def _c2p_stale_domain(self, cutoff):
        return [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("priority", "in", list(HIGH_PRIORITIES)),
            # Won opportunities sit at 100; lost ones are archived, so `active`
            # already excludes them.
            ("probability", "<", 100),
            ("activity_ids", "=", False),
            ("write_date", "<=", cutoff),
        ]

    @api.model
    def _cron_flag_stale_opportunities(self, limit=STALE_LIMIT, dry_run=None):
        """Raise a To-Do on high-priority opportunities that have gone quiet."""
        dry_run = dry_run_enabled(self.env, dry_run)
        todo = activity_type(self.env, "mail.mail_activity_data_todo")
        cutoff = fields.Datetime.now() - timedelta(days=STALE_DAYS)
        leads = self.search(
            self._c2p_stale_domain(cutoff), limit=limit, order="write_date asc"
        )
        flagged = already_flagged(
            self.env, "crm.lead", leads.ids, todo.id, STALE_SUMMARY
        )
        deadline = fields.Date.context_today(self)
        acted = 0
        for lead in leads:
            if lead.id in flagged:
                continue
            acted += 1
            if dry_run:
                continue
            lead.activity_schedule(
                activity_type_id=todo.id,
                summary=STALE_SUMMARY,
                note="No activity on this opportunity for %s days or more. "
                "Expected revenue: %s." % (STALE_DAYS, lead.expected_revenue or 0),
                user_id=(lead.user_id or self.env.user).id,
                date_deadline=deadline,
            )
        return log_run(self.env, "stale_opportunity", len(leads), acted, dry_run, limit)

    # ------------------------------------------------------------------
    # Agent 3 — proposal follow-up
    # ------------------------------------------------------------------
    @api.model
    def _c2p_proposal_stage_ids(self):
        """Stages that read as proposal stages, matched by name at run time.

        Name matching is the trade-off taken for a smaller CRM footprint: no
        extra field on crm.stage, no extra view. The cost is that renaming a
        stage out of these hints stops it being selected — which is why a run
        that matches nothing says so in its note instead of quietly reporting a
        zero that looks like a quiet week.
        """
        stages = self.env["crm.stage"].search([])
        return stages.filtered(
            lambda stage: any(
                hint in (stage.name or "").lower() for hint in PROPOSAL_STAGE_HINTS
            )
        ).ids

    @api.model
    def _c2p_proposal_domain(self, cutoff, stage_ids):
        return [
            ("active", "=", True),
            ("stage_id", "in", stage_ids),
            ("probability", "<", 100),
            ("activity_ids", "=", False),
            ("date_last_stage_update", "<=", cutoff),
        ]

    @api.model
    def _cron_followup_proposals(self, limit=PROPOSAL_LIMIT, dry_run=None):
        """Raise a Call on leads parked in a proposal stage.

        Selects on ``date_last_stage_update`` — time in *this* stage — rather
        than ``write_date``, so editing an unrelated field does not reset the
        clock on a proposal nobody has chased.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        call = activity_type(self.env, "mail.mail_activity_data_call")

        stage_ids = self._c2p_proposal_stage_ids()
        if not stage_ids:
            return log_run(
                self.env,
                "proposal_followup",
                0,
                0,
                dry_run,
                limit,
                note="no CRM stage name contains any of %s, so nothing could be "
                "selected — check CRM > Configuration > Stages"
                % (", ".join(PROPOSAL_STAGE_HINTS),),
            )

        cutoff = fields.Datetime.now() - timedelta(days=PROPOSAL_DAYS)
        leads = self.search(
            self._c2p_proposal_domain(cutoff, stage_ids),
            limit=limit,
            order="date_last_stage_update asc",
        )
        flagged = already_flagged(
            self.env, "crm.lead", leads.ids, call.id, PROPOSAL_SUMMARY
        )
        deadline = fields.Date.context_today(self)
        acted = 0
        for lead in leads:
            if lead.id in flagged:
                continue
            acted += 1
            if dry_run:
                continue
            lead.activity_schedule(
                activity_type_id=call.id,
                summary=PROPOSAL_SUMMARY,
                note="In %s for %s days or more with no activity scheduled."
                % (lead.stage_id.name or "a proposal stage", PROPOSAL_DAYS),
                user_id=(lead.user_id or self.env.user).id,
                date_deadline=deadline,
            )
        return log_run(self.env, "proposal_followup", len(leads), acted, dry_run, limit)

    # ------------------------------------------------------------------
    # Agent 5 — email validation
    # ------------------------------------------------------------------
    @api.model
    def _cron_validate_emails(self, limit=EMAIL_VALIDATION_LIMIT, dry_run=None):
        """Validate addresses that have never been checked.

        Selects only `unknown` leads, so a run costs one pass over the backlog
        and then settles to whatever came in that day. To re-check everything,
        reset the field: `leads.write({"c2p_email_validity": "unknown"})`.

        A note on dry run: this agent still performs DNS lookups when dry, since
        that is what makes the reported verdicts real. Dry run means nothing is
        written to your database — it does not mean no outbound traffic. If the
        Odoo host cannot reach a resolver, the domain layer degrades to "not
        checked" rather than condemning every address.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        leads = self.search(
            [
                ("active", "=", True),
                ("email_from", "!=", False),
                ("c2p_email_validity", "=", "unknown"),
            ],
            limit=limit,
            order="create_date desc",
        )
        # One lookup per domain for the whole batch, not one per lead.
        domain_cache = {}
        checked_on = fields.Datetime.now()
        counts = {VALID: 0, RISKY: 0, INVALID: 0}
        for lead in leads:
            verdict, detail = validate_address(lead.email_from, domain_cache)
            counts[verdict] += 1
            if dry_run:
                continue
            lead.write(
                {
                    "c2p_email_validity": verdict,
                    "c2p_email_validity_detail": detail[:255],
                    "c2p_email_checked_on": checked_on,
                }
            )
        note = "valid=%s risky=%s invalid=%s over %s domain(s)" % (
            counts[VALID],
            counts[RISKY],
            counts[INVALID],
            len(domain_cache),
        )
        return log_run(
            self.env, "email_validation", len(leads), len(leads), dry_run, limit, note
        )
