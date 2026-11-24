from datetime import date, datetime

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

G = "c2p_project_tracker.group_c2p_%s"


@tagged("post_install", "-at_install")
class TestPlanControl(TransactionCase):
    """Synthetic data: a TEST engagement in one company, its delivery project
    in another, a delivery owner and an outsourced contributor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.consult = env["res.company"].create({"name": "TEST Consultants"})
        cls.solutions = env["res.company"].create({"name": "TEST Solutions"})
        both = [(6, 0, [cls.consult.id, cls.solutions.id])]
        only_sol = [(6, 0, [cls.solutions.id])]

        def user(login, group, company, companies):
            return env["res.users"].with_context(no_reset_password=True).create({
                "name": "TEST " + login, "login": login,
                "company_id": company.id, "company_ids": companies,
                "group_ids": [(6, 0, [env.ref("base.group_user").id,
                                      env.ref(group).id])]})

        cls.owner = user("t-owner", G % "portfolio_manager", cls.consult, both)
        cls.lead = user("t-lead", G % "delivery_lead", cls.solutions, only_sol)
        cls.contrib = user("t-contrib", "project.group_project_user",
                           cls.solutions, only_sol)
        cls.other = user("t-other", "project.group_project_user",
                         cls.solutions, only_sol)
        client = env["res.partner"].create(
            {"name": "TEST Client", "is_company": True})
        Project = env["project.project"]
        cls.portfolio = Project.create({
            "name": "TEST – Engagement", "company_id": cls.consult.id,
            "partner_id": client.id, "c2p_layer": "portfolio",
            "account_manager_id": cls.owner.id})
        cls.delivery = Project.create({
            "name": "TEST – Delivery", "company_id": cls.solutions.id,
            "partner_id": client.id, "c2p_layer": "delivery",
            "user_id": cls.lead.id, "privacy_visibility": "followers",
            "allow_milestones": True})
        cls.portfolio.c2p_counterpart_id = cls.delivery
        # The delivery owner invites contributors to the project they work on.
        cls.delivery.message_subscribe(
            partner_ids=(cls.contrib | cls.other).partner_id.ids)
        cls.milestone = env["project.milestone"].create({
            "name": "TEST M1", "project_id": cls.delivery.id,
            "deadline": date(2027, 1, 20)})
        cls.task = env["project.task"].create({
            "name": "TEST build import", "project_id": cls.delivery.id,
            "milestone_id": cls.milestone.id,
            "user_ids": [(6, 0, [cls.contrib.id])],
            "date_deadline": datetime(2027, 1, 10, 12, 0),
            "c2p_acceptance_criteria": "TEST: 500 rows reconcile."})

    def _propose(self, user=None, **vals):
        base = {"task_id": self.task.id, "change_type": "date",
                "new_deadline": date(2027, 1, 17),
                "reason": "TEST: client data arrived late"}
        base.update(vals)
        return self.env["c2p.plan.change"].with_user(
            user or self.contrib).create(base)

    # ── contributors cannot move the plan silently ───────────────────────
    def test_contributor_cannot_change_committed_plan_fields(self):
        task = self.task.with_user(self.contrib)
        for vals in ({"date_deadline": datetime(2027, 2, 1, 12, 0)},
                     {"user_ids": [(6, 0, [self.other.id])]},
                     {"c2p_acceptance_criteria": "Anything will do."}):
            with self.subTest(vals=list(vals)), self.assertRaises(UserError):
                task.write(vals)
        self.task.invalidate_recordset()
        self.assertEqual(self.task.date_deadline, datetime(2027, 1, 10, 12, 0))
        self.assertEqual(self.task.user_ids, self.contrib)

    def test_contributor_can_still_report_progress(self):
        self.task.with_user(self.contrib).write({"description": "<p>50%</p>"})

    def test_contributor_cannot_move_a_milestone(self):
        with self.assertRaises(UserError):
            self.milestone.with_user(self.contrib).write(
                {"deadline": date(2027, 3, 1)})

    # ── propose → assess → approve ───────────────────────────────────────
    def test_proposal_is_signed_and_cannot_be_self_approved(self):
        change = self._propose(state="approved", decided_by_id=self.contrib.id)
        self.assertEqual(change.state, "proposed")
        self.assertEqual(change.proposed_by_id, self.contrib)
        self.assertFalse(change.decided_by_id)
        self.assertIn("TEST M1", change.affected_deliverables)
        with self.assertRaises(AccessError):
            change.action_approve()
        self.assertEqual(self.task.date_deadline, datetime(2027, 1, 10, 12, 0))

    def test_delivery_owner_approves_and_the_original_date_stays(self):
        change = self._propose()
        change.with_user(self.lead).action_approve()
        self.assertEqual(change.state, "approved")
        self.assertEqual(change.decided_by_id, self.lead)
        self.assertTrue(change.decided_on)
        self.assertEqual(change.previous_value, "2027-01-10")
        self.assertEqual(change.new_value, "2027-01-17")
        self.assertEqual(change.baseline_deadline, date(2027, 1, 10))
        self.assertEqual(change.reason, "TEST: client data arrived late")
        self.assertEqual(self.task.date_deadline.date(), date(2027, 1, 17))
        with self.assertRaises(UserError):
            change.with_user(self.lead).action_approve()

    def test_decided_change_is_immutable_and_never_deleted(self):
        change = self._propose()
        change.with_user(self.lead).action_approve()
        with self.assertRaises(UserError):
            change.with_user(self.lead).write({"reason": "rewritten"})
        with self.assertRaises(UserError):
            change.with_user(self.lead).write({"previous_value": "x"})
        with self.assertRaises(UserError):
            change.unlink()

    def test_reject_needs_a_note(self):
        change = self._propose()
        with self.assertRaises(UserError):
            change.with_user(self.lead).action_reject()
        change.with_user(self.lead).write({"decision_note": "TEST: no slack"})
        change.with_user(self.lead).action_reject()
        self.assertEqual(change.state, "rejected")
        self.assertEqual(self.task.date_deadline, datetime(2027, 1, 10, 12, 0))

    def test_reassignment_records_previous_and_new_assignee(self):
        change = self._propose(user=self.lead, change_type="reassign",
                               new_user_id=self.other.id, new_deadline=False)
        change.with_user(self.lead).action_approve()
        self.assertEqual(self.task.user_ids, self.other)
        self.assertEqual(change.previous_value, self.contrib.name)
        self.assertEqual(change.new_value, self.other.name)

    # ── milestone dates: baseline, forecast, notification ────────────────
    def test_milestone_date_change_keeps_baseline_and_notifies_owner(self):
        change = self._propose(task_id=False, milestone_id=self.milestone.id,
                               new_deadline=date(2027, 1, 27), user=self.lead)
        change.with_user(self.lead).action_approve()
        self.assertEqual(self.milestone.deadline, date(2027, 1, 27))
        self.assertEqual(self.milestone.c2p_baseline_deadline, date(2027, 1, 20))
        self.assertEqual(change.baseline_deadline, date(2027, 1, 20))
        activity = self.env["mail.activity"].search([
            ("res_model", "=", "project.project"),
            ("res_id", "=", self.portfolio.id),
            ("user_id", "=", self.owner.id)])
        self.assertEqual(len(activity), 1)
        self.assertIn("2027-01-20", activity.note)
        # A second move keeps the first baseline.
        again = self._propose(task_id=False, milestone_id=self.milestone.id,
                              new_deadline=date(2027, 2, 3), user=self.lead)
        again.with_user(self.lead).action_approve()
        self.assertEqual(self.milestone.c2p_baseline_deadline, date(2027, 1, 20))
        with self.assertRaises(UserError):
            self.milestone.with_user(self.lead).write(
                {"c2p_baseline_deadline": date(2027, 2, 3)})

    # ── the delivery owner's own edits are on record too ─────────────────
    def test_direct_edit_by_delivery_owner_is_logged(self):
        self.task.with_user(self.lead).with_context(
            c2p_plan_reason="TEST: rebalanced the week").write(
            {"date_deadline": datetime(2027, 1, 12, 12, 0)})
        log = self.task.c2p_plan_change_ids
        self.assertEqual(len(log), 1)
        self.assertTrue(log.direct_edit)
        self.assertEqual(log.state, "approved")
        self.assertEqual(log.decided_by_id, self.lead)
        self.assertEqual((log.previous_value, log.new_value),
                         ("2027-01-10", "2027-01-12"))
        self.assertEqual(log.reason, "TEST: rebalanced the week")

    def test_direct_milestone_edit_keeps_baseline_and_notifies(self):
        self.milestone.with_user(self.lead).write({"deadline": date(2027, 1, 25)})
        self.assertEqual(self.milestone.c2p_baseline_deadline, date(2027, 1, 20))
        self.assertTrue(self.milestone.c2p_plan_change_ids.direct_edit)
        self.assertTrue(self.env["mail.activity"].search_count([
            ("res_model", "=", "project.project"),
            ("res_id", "=", self.portfolio.id),
            ("user_id", "=", self.owner.id)]))

    def test_first_planning_is_not_a_plan_change(self):
        task = self.env["project.task"].create({
            "name": "TEST unplanned", "project_id": self.delivery.id,
            "user_ids": False})
        task.with_user(self.lead).write({
            "date_deadline": datetime(2027, 1, 5, 12, 0),
            "user_ids": [(6, 0, [self.contrib.id])]})
        self.assertFalse(task.c2p_plan_change_ids)

    # ── scope goes to Consultants ────────────────────────────────────────
    def test_scope_change_cannot_be_approved_by_delivery(self):
        change = self._propose(change_type="scope", new_deadline=False,
                               reason="TEST: client wants payroll too",
                               details="Add payroll module")
        with self.assertRaises(UserError):
            change.with_user(self.lead).action_approve()
        self.assertEqual(change.state, "proposed")

    def test_scope_change_becomes_one_consultants_change_request(self):
        Request = self.env["c2p.change.request"]
        before = Request.search_count([])
        change = self._propose(change_type="scope", new_deadline=False,
                               reason="TEST: client wants payroll too",
                               details="<b>Add payroll</b>")
        with self.assertRaises(AccessError):
            change.action_send_to_consultants()
        change.with_user(self.lead).action_send_to_consultants()
        self.assertEqual(change.state, "escalated")
        request = change.change_request_id.sudo()
        self.assertEqual(request.project_id, self.portfolio)
        self.assertEqual(request.state, "draft")
        self.assertNotIn("<b>Add payroll</b>", request.description)
        self.assertEqual(Request.search_count([]), before + 1)
        with self.assertRaises(UserError):
            change.with_user(self.lead).action_send_to_consultants()
        self.assertEqual(Request.search_count([]), before + 1)
        # Nothing in the plan moved, and the contract value is untouched
        # until Consultants approve through their own flow.
        self.assertEqual(self.task.date_deadline, datetime(2027, 1, 10, 12, 0))
        self.assertEqual(self.portfolio.contract_value, 0)
        request.with_user(self.owner).action_submit()
        request.with_user(self.owner).action_approve()
        self.assertEqual(change.change_request_state, "approved")

    # ── who sees what ────────────────────────────────────────────────────
    def test_contributor_sees_only_their_own_proposals(self):
        mine = self._propose()
        theirs = self._propose(user=self.lead)
        Change = self.env["c2p.plan.change"]
        self.assertEqual(Change.with_user(self.contrib).search([]), mine)
        self.assertEqual(Change.with_user(self.lead).search(
            [("id", "in", (mine | theirs).ids)]), mine | theirs)
        with self.assertRaises(AccessError):
            mine.with_user(self.contrib).write({"reason": "edited later"})

    def test_consultants_only_user_does_not_see_solutions_changes(self):
        change = self._propose()
        consult_only = self.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "TEST consult", "login": "t-consult-only",
                "company_id": self.consult.id,
                "company_ids": [(6, 0, [self.consult.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                      self.env.ref(G % "delivery_lead").id])]})
        self.assertFalse(self.env["c2p.plan.change"].with_user(
            consult_only).search([("id", "=", change.id)]))
