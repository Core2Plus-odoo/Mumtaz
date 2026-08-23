"""The C2P lead agents, ported from the server actions running on Mumtaz_C2P.

Agents 1-3 are faithful ports of crons 44, 45 and 46 — the scoring weights,
thresholds, activity summaries and deadlines below are the ones actually in
production, read out of `ir_act_server.code` on 2026-08-10, not invented here.
Where this module deliberately departs from the original, the comment says so.

What the port adds is the scaffolding the database version could not have: a
dry-run mode, a per-run audit row, tests, and a limit that is a reviewable
constant rather than a literal buried in a database field.

Agents 6 and 7 are new — they were not in the original set.
"""

from datetime import timedelta

from odoo import api, fields, models

from .agent_tools import activity_type, already_flagged, dry_run_enabled, log_run
from .email_validation import (
    INVALID,
    RISKY,
    VALID,
    address_domain,
    validate_address,
)

# --------------------------------------------------------------------------
# Agent 1 — scoring weights, as they run in production.
# --------------------------------------------------------------------------

# Substring matches against the lowercased UTM source name. Both rules can fire
# on one lead — a source named "Meta referral" scores 45, not 25. That is the
# original behaviour, and it is additive on purpose.
SOURCE_SIGNALS = (
    (("whatsapp", "ctwa", "meta"), 20),
    (("referral", "apollo"), 25),
)

# Flat 20 for any of the six. Note there is no Pakistan here: the production
# rule scores GCC only.
GCC_COUNTRY_CODES = ("AE", "SA", "OM", "QA", "BH", "KW")
SCORE_GCC = 20

# Matched as substrings of the whole address, with the trailing dot, exactly as
# production does — "gmail." catches gmail.com and gmail.co.uk alike. This is a
# separate, shorter list from the one email_validation.py uses for deliverability
# verdicts; they answer different questions and are kept apart on purpose.
FREE_EMAIL_MARKERS = ("gmail.", "yahoo.", "hotmail.", "outlook.", "icloud.")
SCORE_BUSINESS_EMAIL = 20

# (expected revenue at or above, points). First match wins.
REVENUE_BANDS = ((30000, 25), (7000, 10))

SCORE_PHONE = 10
SCORE_CONTACT_NAME = 5
# An existing activity is read as evidence somebody is working the lead.
SCORE_HAS_ACTIVITY = 5

# (total score at or above, crm.lead priority). First match wins.
PRIORITY_BANDS = ((65, "3"), (45, "2"), (25, "1"))
PRIORITY_FLOOR = "0"

# --------------------------------------------------------------------------
# Agent settings — production values.
# --------------------------------------------------------------------------

LEAD_SCORING_LIMIT = 4000

STALE_DAYS = 21
STALE_LIMIT = 40
STALE_DEADLINE_DAYS = 2

PROPOSAL_DAYS = 7
PROPOSAL_LIMIT = 40
PROPOSAL_DEADLINE_DAYS = 1

# Exact stage names, as production matches them. Not a fuzzy match: the two
# stages mean different things and the agent says something different in each.
PROPOSAL_STAGE_SENT = "Proposal Sent"
PROPOSAL_STAGE_PENDING = "Proposal to be Send"
PROPOSAL_STAGE_NAMES = (PROPOSAL_STAGE_SENT, PROPOSAL_STAGE_PENDING)

EMAIL_VALIDATION_LIMIT = 100

# Coverage agents — new, not part of the ported set.
OWNER_ASSIGNMENT_LIMIT = 50
COVERAGE_LIMIT = 50
COVERAGE_GRACE_DAYS = 3

HIGH_PRIORITIES = ("2", "3")

# The production summaries, character for character. Keeping them identical is
# what stops this module re-nagging every lead the database agents already
# flagged: an activity raised last week by cron 45 still matches, so the ported
# agent skips it instead of raising a second one beside it.
STALE_SUMMARY = "Stale - no contact in 21 days"
PROPOSAL_SENT_SUMMARY = "Proposal follow-up call"
PROPOSAL_PENDING_SUMMARY = "Proposal still not sent - issue it today"
COVERAGE_SUMMARY = "C2P Agent: no next step"

_STALE_NOTE = (
    "<p>This opportunity has had no activity for 21 days and is rated high "
    "priority. Decide one of three things: re-engage with a specific reason, "
    "move it to Project Onhold with a note, or mark it Lost with a reason.</p>"
)
_PROPOSAL_SENT_NOTE = (
    "<p>Seven days in this stage with no next action.</p>"
    "<p>Call rather than email. Ask what is outstanding on their side and "
    "whether the scope still matches. Do not lead with a discount to a problem "
    "you have not diagnosed.</p>"
)
_PROPOSAL_PENDING_NOTE = (
    "<p>This has sat in 'Proposal to be Send' for over a week. Either issue the "
    "proposal today or move the record to a stage that reflects reality.</p>"
)


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
    c2p_scored_on = fields.Datetime(
        readonly=True,
        copy=False,
        index=True,
        help="When the scoring agent last looked at this lead. Blank means "
        "never scored — those are taken first, so the backlog drains.",
    )
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

        `mobile` is deliberately absent from the depends: the field has come and
        gone from crm.lead across versions, and naming one that does not exist
        fails the registry at install.
        """
        for lead in self:
            if lead.email_from and lead.c2p_email_validity != INVALID:
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
        """Used for outreach routing only — scoring reads `phone` alone, as
        production does."""
        self.ensure_one()
        mobile = self.mobile if "mobile" in self._fields else False
        return bool(self.phone or mobile)

    def _c2p_lead_score(self):
        """Total the production scoring rules for one lead. No side effects."""
        self.ensure_one()
        score = 0

        source = (self.source_id.name or "").lower() if self.source_id else ""
        for keywords, points in SOURCE_SIGNALS:
            if any(keyword in source for keyword in keywords):
                score += points

        if self.country_id and self.country_id.code in GCC_COUNTRY_CODES:
            score += SCORE_GCC

        email = (self.email_from or "").lower()
        if email and "@" in email:
            if not any(marker in email for marker in FREE_EMAIL_MARKERS):
                score += SCORE_BUSINESS_EMAIL

        for threshold, points in REVENUE_BANDS:
            if self.expected_revenue and self.expected_revenue >= threshold:
                score += points
                break

        if self.phone:
            score += SCORE_PHONE
        if self.contact_name:
            score += SCORE_CONTACT_NAME
        if self.activity_ids:
            score += SCORE_HAS_ACTIVITY

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
    def _c2p_scoring_domain(self):
        return [
            ("active", "=", True),
            ("stage_id.is_won", "=", False),
            ("probability", "<", 100),
        ]

    @api.model
    def _c2p_scoring_batch(self, limit):
        """Never-scored leads first, then the longest-unrescored.

        Two searches rather than one ordered query, because "nulls first" is not
        expressible in an Odoo order string — Postgres sorts NULLs last on ASC,
        which would put never-scored leads permanently at the back of the queue.
        """
        domain = self._c2p_scoring_domain()
        never = self.search(domain + [("c2p_scored_on", "=", False)], limit=limit)
        if len(never) >= limit:
            return never
        stale = self.search(
            domain + [("c2p_scored_on", "!=", False)],
            limit=limit - len(never),
            order="c2p_scored_on asc",
        )
        return never | stale

    def _c2p_stamp_scored(self, when):
        """Record the pass WITHOUT touching write_date.

        Raw SQL, and load-bearing. A normal write() bumps write_date, and the
        stale-lead agent selects on `write_date` older than 21 days — so
        stamping through the ORM would refresh every lead the scorer touched and
        the stale agent would never select anything again. The two agents run on
        the same records nightly, so this is not a theoretical interaction.
        """
        if not self:
            return
        self.env.cr.execute(
            "UPDATE crm_lead SET c2p_scored_on = %s WHERE id IN %s",
            (when, tuple(self.ids)),
        )
        self.invalidate_recordset(["c2p_scored_on"])

    @api.model
    def _cron_score_leads(self, limit=LEAD_SCORING_LIMIT, dry_run=None):
        """Set priority on ``crm.lead`` from the production scoring rules.

        Only writes `priority` where it actually changed — as production does,
        and for the same reason: a write on every lead every night would churn
        write_date across the whole pipeline.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        leads = self._c2p_scoring_batch(limit)
        acted = 0
        for lead in leads:
            priority = lead._c2p_lead_priority()
            if priority == lead.priority:
                continue
            acted += 1
            if not dry_run:
                lead.priority = priority
        if not dry_run:
            leads._c2p_stamp_scored(fields.Datetime.now())
        remaining = self.search_count(
            self._c2p_scoring_domain() + [("c2p_scored_on", "=", False)]
        )
        note = "%s never-scored lead(s) still in the backlog" % remaining
        return log_run(
            self.env, "lead_scoring", len(leads), acted, dry_run, limit, note
        )

    # ------------------------------------------------------------------
    # Agent 2 — stale lead detection
    # ------------------------------------------------------------------
    @api.model
    def _c2p_stale_domain(self, cutoff):
        return [
            ("active", "=", True),
            ("type", "=", "opportunity"),
            ("stage_id.is_won", "=", False),
            ("probability", "<", 100),
            ("write_date", "<", cutoff),
            ("activity_ids", "=", False),
            ("priority", "in", list(HIGH_PRIORITIES)),
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
        deadline = fields.Date.context_today(self) + timedelta(
            days=STALE_DEADLINE_DAYS
        )
        acted = 0
        ownerless = 0
        for lead in leads:
            # Production skips a lead with no owner rather than assigning the
            # task to whoever ran the cron. Agent 6 is what fixes those.
            owner = lead.user_id or lead.team_id.user_id
            if not owner:
                ownerless += 1
                continue
            if lead.id in flagged:
                continue
            acted += 1
            if dry_run:
                continue
            lead.activity_schedule(
                activity_type_id=todo.id,
                summary=STALE_SUMMARY,
                note=_STALE_NOTE,
                user_id=owner.id,
                date_deadline=deadline,
            )
        note = "%s lead(s) skipped for having no owner" % ownerless if ownerless else ""
        return log_run(
            self.env, "stale_opportunity", len(leads), acted, dry_run, limit, note
        )

    # ------------------------------------------------------------------
    # Agent 3 — proposal follow-up
    # ------------------------------------------------------------------
    @api.model
    def _c2p_proposal_stages(self):
        return self.env["crm.stage"].search(
            [("name", "in", list(PROPOSAL_STAGE_NAMES))]
        )

    @api.model
    def _c2p_proposal_domain(self, cutoff, stage_ids):
        return [
            ("active", "=", True),
            ("stage_id", "in", stage_ids),
            ("date_last_stage_update", "<", cutoff),
            ("activity_ids", "=", False),
        ]

    @api.model
    def _cron_followup_proposals(self, limit=PROPOSAL_LIMIT, dry_run=None):
        """Chase leads parked in a proposal stage.

        Two stages, two different messages: "Proposal Sent" gets a follow-up
        call, "Proposal to be Send" gets told to issue the thing. Production
        matches those names exactly, so this does too — but a run that matches
        no stage at all now says so in its note rather than reporting a zero
        that reads like a quiet week.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        call = activity_type(self.env, "mail.mail_activity_data_call")

        stages = self._c2p_proposal_stages()
        if not stages:
            return log_run(
                self.env, "proposal_followup", 0, 0, dry_run, limit,
                note="no crm.stage is named %s — nothing could be selected"
                % " or ".join(PROPOSAL_STAGE_NAMES),
            )

        cutoff = fields.Datetime.now() - timedelta(days=PROPOSAL_DAYS)
        leads = self.search(
            self._c2p_proposal_domain(cutoff, stages.ids),
            limit=limit,
            order="date_last_stage_update asc",
        )
        flagged = already_flagged(
            self.env, "crm.lead", leads.ids, call.id, PROPOSAL_SENT_SUMMARY
        ) | already_flagged(
            self.env, "crm.lead", leads.ids, call.id, PROPOSAL_PENDING_SUMMARY
        )
        deadline = fields.Date.context_today(self) + timedelta(
            days=PROPOSAL_DEADLINE_DAYS
        )
        acted = 0
        ownerless = 0
        for lead in leads:
            owner = lead.user_id or lead.team_id.user_id
            if not owner:
                ownerless += 1
                continue
            if lead.id in flagged:
                continue
            sent = lead.stage_id.name == PROPOSAL_STAGE_SENT
            acted += 1
            if dry_run:
                continue
            lead.activity_schedule(
                activity_type_id=call.id,
                summary=PROPOSAL_SENT_SUMMARY if sent else PROPOSAL_PENDING_SUMMARY,
                note=_PROPOSAL_SENT_NOTE if sent else _PROPOSAL_PENDING_NOTE,
                user_id=owner.id,
                date_deadline=deadline,
            )
        note = "%s lead(s) skipped for having no owner" % ownerless if ownerless else ""
        return log_run(
            self.env, "proposal_followup", len(leads), acted, dry_run, limit, note
        )

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

    # ------------------------------------------------------------------
    # Agent 6 — owner assignment
    # ------------------------------------------------------------------
    @api.model
    def _c2p_assignable_users(self, team):
        """Salespeople who may receive a lead.

        Prefers the lead's own sales team; falls back to everyone in the
        salesman group. Note the v19 spelling: `res.groups.users` was removed,
        so membership is read from the user side via `group_ids`.
        """
        if team and team.member_ids:
            return team.member_ids.filtered("active")
        group = self.env.ref("sales_team.group_sale_salesman", raise_if_not_found=False)
        if not group:
            return self.env["res.users"]
        return self.env["res.users"].search(
            [("group_ids", "in", group.id), ("active", "=", True)]
        )

    @api.model
    def _c2p_open_lead_load(self, users):
        """How many open leads each candidate already carries.

        One grouped query, not one count per user. Assigning to the lightest
        load is self-balancing in a way round-robin is not: it corrects for
        leads that arrived by any other route.
        """
        if not users:
            return {}
        rows = self._read_group(
            [
                ("user_id", "in", users.ids),
                ("active", "=", True),
                ("probability", "<", 100),
            ],
            groupby=["user_id"],
            aggregates=["__count"],
        )
        return {user.id: count for user, count in rows}

    @api.model
    def _cron_assign_owners(self, limit=OWNER_ASSIGNMENT_LIMIT, dry_run=None):
        """Give every unassigned open lead a salesperson.

        A lead with no owner is nobody's problem, so it is the one state from
        which a lead never recovers on its own. Selection is exactly the
        unassigned, so this drains and then handles the day's intake.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        leads = self.search(
            [
                ("active", "=", True),
                ("user_id", "=", False),
                ("probability", "<", 100),
            ],
            limit=limit,
            order="create_date asc",
        )
        # Candidates per team, resolved once each rather than per lead.
        candidate_cache = {}

        def candidates_for(team):
            key = team.id or 0
            if key not in candidate_cache:
                candidate_cache[key] = self._c2p_assignable_users(team)
            return candidate_cache[key]

        everyone = self.env["res.users"]
        for lead in leads:
            everyone |= candidates_for(lead.team_id)
        # One grouped query for the whole batch. Load is then tracked in memory
        # so fifty leads spread across the team rather than all landing on
        # whoever happened to start the night quietest.
        load_by_user = self._c2p_open_lead_load(everyone)

        acted = 0
        skipped = 0
        for lead in leads:
            candidates = candidates_for(lead.team_id)
            if not candidates:
                skipped += 1
                continue
            chosen = min(candidates, key=lambda u: (load_by_user.get(u.id, 0), u.id))
            load_by_user[chosen.id] = load_by_user.get(chosen.id, 0) + 1
            acted += 1
            if not dry_run:
                lead.user_id = chosen
        note = "no salesperson available for %s lead(s)" % skipped if skipped else ""
        return log_run(
            self.env, "owner_assignment", len(leads), acted, dry_run, limit, note
        )

    # ------------------------------------------------------------------
    # Agent 7 — guaranteed next step
    # ------------------------------------------------------------------
    @api.model
    def _c2p_coverage_domain(self, cutoff):
        return [
            ("active", "=", True),
            ("probability", "<", 100),
            ("user_id", "!=", False),
            ("activity_ids", "=", False),
            ("create_date", "<=", cutoff),
        ]

    @api.model
    def _cron_ensure_next_step(self, limit=COVERAGE_LIMIT, dry_run=None):
        """Every open lead with an owner and no scheduled action gets one.

        The stale and proposal agents chase specific situations; this is the
        floor beneath them — a lead nobody has scheduled anything on is a lead
        nobody is working, whatever its priority or stage.

        Deliberately runs after a grace period and under a low limit. On a
        database with thousands of untouched leads this would otherwise create
        thousands of activities on its first night, which is a worse outcome
        than the silence it replaces. Watch the run log's backlog figure and
        raise the limit deliberately.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        todo = activity_type(self.env, "mail.mail_activity_data_todo")
        cutoff = fields.Datetime.now() - timedelta(days=COVERAGE_GRACE_DAYS)
        leads = self.search(
            self._c2p_coverage_domain(cutoff), limit=limit, order="create_date asc"
        )
        flagged = already_flagged(
            self.env, "crm.lead", leads.ids, todo.id, COVERAGE_SUMMARY
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
                summary=COVERAGE_SUMMARY,
                note="This lead has no scheduled next step and has been open "
                "since %s. Decide the next action or mark it lost."
                % (lead.create_date and lead.create_date.date() or "creation"),
                user_id=lead.user_id.id,
                date_deadline=deadline,
            )
        remaining = self.search_count(self._c2p_coverage_domain(cutoff))
        if dry_run:
            # Nothing was created, so the leads just counted are still in the
            # domain. On a live run the new activities have already removed them.
            remaining = max(0, remaining - acted)
        note = "%s lead(s) still with no next step" % remaining
        return log_run(
            self.env, "coverage_followup", len(leads), acted, dry_run, limit, note
        )
