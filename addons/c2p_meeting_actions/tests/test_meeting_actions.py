from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestMeetingActions(TransactionCase):
    """Minutes, approval, and conversion that happens exactly once.

    The duplicate guard is the thing to pin. A Python check-then-create reads
    correct and fails under concurrency, so the tests below assert the database
    constraint directly rather than only the happy path through the method.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Meeting = cls.env["c2p.meeting"]
        cls.Action = cls.env["c2p.meeting.action"]
        cls.Task = cls.env["project.task"]

        cls.approver_group = cls.env.ref(
            "c2p_meeting_actions.group_c2p_meeting_approver")
        cls.user_group = cls.env.ref("project.group_project_user")

        cls.chair = cls.env["res.users"].create({
            "name": "Chair Person", "login": "chair.mom@example.com",
            "groups_id": [(6, 0, [cls.user_group.id, cls.approver_group.id])],
        })
        cls.member = cls.env["res.users"].create({
            "name": "Team Member", "login": "member.mom@example.com",
            "groups_id": [(6, 0, [cls.user_group.id])],
        })
        cls.project = cls.env["project.project"].create(
            {"name": "MoM Test Project", "allow_milestones": True})

    def _meeting(self, **vals):
        base = {
            "title": "Weekly delivery review",
            "project_id": self.project.id,
            "organiser_id": self.chair.id,
            "attendee_ids": [(6, 0, [self.chair.partner_id.id,
                                     self.member.partner_id.id])],
        }
        base.update(vals)
        return self.Meeting.with_user(self.chair).create(base)

    def _action(self, meeting, **vals):
        base = {"meeting_id": meeting.id, "name": "Send the revised plan",
                "user_id": self.member.id}
        base.update(vals)
        return self.Action.with_user(self.chair).create(base)

    # ── references ──────────────────────────────────────────────────────
    def test_meeting_gets_a_sequence_reference(self):
        meeting = self._meeting()
        self.assertTrue(meeting.reference)
        self.assertNotEqual(meeting.reference, "New")
        self.assertIn("MOM/", meeting.reference)

    def test_action_reference_derives_from_the_meeting(self):
        meeting = self._meeting()
        a1 = self._action(meeting)
        a2 = self._action(meeting, name="Book the UAT session")
        self.assertEqual(a1.reference, f"{meeting.reference}-A1")
        self.assertEqual(a2.reference, f"{meeting.reference}-A2")

    def test_action_reference_skips_numbers_already_taken(self):
        """Deleting A2 must not make the next action collide with A3."""
        meeting = self._meeting()
        self._action(meeting)
        a2 = self._action(meeting, name="Second")
        a3 = self._action(meeting, name="Third")
        a2.unlink()
        a4 = self._action(meeting, name="Fourth")
        self.assertEqual(a3.reference, f"{meeting.reference}-A3")
        self.assertEqual(a4.reference, f"{meeting.reference}-A2",
                         "the freed number is reused, and never duplicated")

    @mute_logger("odoo.sql_db")
    def test_two_actions_cannot_share_a_reference(self):
        meeting = self._meeting()
        a1 = self._action(meeting)
        a2 = self._action(meeting, name="Another")
        with self.assertRaises(IntegrityError):
            a2.reference = a1.reference
            a2.flush_recordset()

    # ── the duplicate guard, at the database ────────────────────────────
    @mute_logger("odoo.sql_db")
    def test_the_database_refuses_two_tasks_for_one_action(self):
        """This is the control that makes conversion concurrency-safe.

        Two simultaneous requests cannot both pass a Python check, but they
        cannot both pass this. A real two-process race cannot be written
        reliably inside a transaction test, so the constraint itself is what
        gets asserted.
        """
        ref = "MOM/9999/0001-A1"
        self.Task.create({"name": "First", "project_id": self.project.id,
                          "c2p_meeting_action_ref": ref})
        with self.assertRaises(IntegrityError):
            self.Task.create({"name": "Second",
                              "project_id": self.project.id,
                              "c2p_meeting_action_ref": ref})
            self.env.flush_all()

    def test_tasks_without_a_reference_are_unconstrained(self):
        """NULLs are distinct under a UNIQUE constraint, so ordinary tasks —
        the overwhelming majority — are unaffected."""
        tasks = self.Task.create([
            {"name": "Ordinary one", "project_id": self.project.id},
            {"name": "Ordinary two", "project_id": self.project.id},
        ])
        self.env.flush_all()
        self.assertEqual(len(tasks), 2)
        self.assertFalse(any(t.c2p_meeting_action_ref for t in tasks))

    def test_duplicating_a_task_does_not_carry_the_reference(self):
        """copy=False matters: a duplicate carrying the reference would collide
        with its own original."""
        meeting = self._meeting()
        action = self._action(meeting)
        action.with_user(self.chair).action_approve()
        task = action.with_user(self.chair).action_create_task()
        clone = task.copy()
        self.env.flush_all()
        self.assertFalse(clone.c2p_meeting_action_ref)

    # ── conversion ──────────────────────────────────────────────────────
    def test_conversion_is_idempotent(self):
        meeting = self._meeting()
        action = self._action(meeting)
        action.with_user(self.chair).action_approve()

        first = action.with_user(self.chair).action_create_task()
        before = self.Task.search_count([("project_id", "=", self.project.id)])
        second = action.with_user(self.chair).action_create_task()
        after = self.Task.search_count([("project_id", "=", self.project.id)])

        self.assertEqual(first, second, "the same task comes back")
        self.assertEqual(before, after, "no second task is created")
        self.assertEqual(action.state, "converted")

    def test_conversion_adopts_an_orphaned_task(self):
        """If a previous attempt created the task but lost its task_id write,
        the action must adopt that task rather than create a rival. A
        Python-only guard would never notice."""
        meeting = self._meeting()
        action = self._action(meeting)
        action.with_user(self.chair).action_approve()

        orphan = self.Task.create({
            "name": "Created by a lost attempt",
            "project_id": self.project.id,
            "c2p_meeting_action_ref": action.reference,
        })
        self.env.flush_all()

        result = action.with_user(self.chair).action_create_task()
        self.assertEqual(result, orphan, "the existing task is adopted")
        self.assertEqual(action.task_id, orphan)

    def test_conversion_copies_the_right_values(self):
        meeting = self._meeting()
        milestone = self.env["project.milestone"].create(
            {"name": "Design gate", "project_id": self.project.id})
        action = self._action(meeting, date_deadline="2030-01-15",
                              milestone_id=milestone.id)
        action.with_user(self.chair).action_approve()
        task = action.with_user(self.chair).action_create_task()

        self.assertEqual(task.name, action.name)
        self.assertEqual(task.project_id, self.project)
        self.assertEqual(task.user_ids, self.member)
        self.assertEqual(str(task.date_deadline), "2030-01-15")
        self.assertEqual(task.milestone_id, milestone)
        self.assertEqual(task.c2p_meeting_action_ref, action.reference)

    def test_task_description_carries_provenance(self):
        meeting = self._meeting()
        action = self._action(meeting, notes="Client asked for this in writing")
        action.with_user(self.chair).action_approve()
        task = action.with_user(self.chair).action_create_task()
        self.assertIn(meeting.reference, task.description or "")
        self.assertIn(action.reference, task.description or "")

    def test_notes_are_escaped_into_the_description(self):
        """Notes are typed by a user, so they must not reach the task
        description as live markup."""
        meeting = self._meeting()
        action = self._action(meeting, notes="<script>alert(1)</script>")
        action.with_user(self.chair).action_approve()
        task = action.with_user(self.chair).action_create_task()
        self.assertNotIn("<script>", task.description or "")
        self.assertIn("&lt;script&gt;", task.description or "")

    def test_an_unapproved_action_cannot_become_a_task(self):
        meeting = self._meeting()
        action = self._action(meeting)
        with self.assertRaises(UserError):
            action.with_user(self.chair).action_create_task()

    def test_an_action_with_no_project_cannot_be_converted(self):
        meeting = self._meeting(project_id=False)
        action = self._action(meeting)
        action.project_id = False
        action.with_user(self.chair).action_approve()
        with self.assertRaises(UserError):
            action.with_user(self.chair).action_create_task()

    def test_converting_a_whole_meeting_only_touches_approved_actions(self):
        meeting = self._meeting()
        approved = self._action(meeting, name="Approved one")
        draft = self._action(meeting, name="Still draft")
        approved.with_user(self.chair).action_approve()
        meeting.with_user(self.chair).action_confirm()

        meeting.with_user(self.chair).action_convert_approved()
        self.assertEqual(approved.state, "converted")
        self.assertEqual(draft.state, "draft")
        self.assertFalse(draft.task_id)

    # ── approval authority ──────────────────────────────────────────────
    def test_a_non_approver_cannot_approve(self):
        meeting = self._meeting()
        action = self._action(meeting)
        action.with_user(self.member).action_propose()
        with self.assertRaises(UserError):
            action.with_user(self.member).action_approve()

    def test_a_non_approver_cannot_reject(self):
        meeting = self._meeting()
        action = self._action(meeting)
        with self.assertRaises(UserError):
            action.with_user(self.member).action_reject("no")

    def test_rejection_needs_a_reason(self):
        meeting = self._meeting()
        action = self._action(meeting)
        with self.assertRaises(UserError):
            action.with_user(self.chair).action_reject("   ")

    def test_rejection_records_the_reason(self):
        meeting = self._meeting()
        action = self._action(meeting)
        action.with_user(self.chair).action_reject("Out of scope for this phase")
        self.assertEqual(action.state, "rejected")
        self.assertEqual(action.rejection_reason, "Out of scope for this phase")
        self.assertEqual(action.approved_by_id, self.chair)

    def test_a_converted_action_cannot_be_rejected(self):
        meeting = self._meeting()
        action = self._action(meeting)
        action.with_user(self.chair).action_approve()
        action.with_user(self.chair).action_create_task()
        with self.assertRaises(UserError):
            action.with_user(self.chair).action_reject("changed my mind")

    def test_self_approval_is_allowed_but_recorded(self):
        """10.1 forbids *silent* self-approval. It is permitted here and
        written into the chatter, so an audit sees it without inferring."""
        meeting = self._meeting()
        action = self._action(meeting)
        action.with_user(self.chair).action_propose()
        before = len(action.message_ids)
        action.with_user(self.chair).action_approve()
        bodies = " ".join(m.body or "" for m in action.message_ids)
        self.assertGreater(len(action.message_ids), before)
        self.assertIn("proposed", bodies.lower())

    # ── minutes lifecycle ───────────────────────────────────────────────
    def test_minutes_need_attendees_before_confirmation(self):
        meeting = self._meeting(attendee_ids=[(6, 0, [])])
        with self.assertRaises(UserError):
            meeting.with_user(self.chair).action_confirm()

    def test_confirmed_minutes_freeze_the_narrative(self):
        meeting = self._meeting()
        meeting.with_user(self.chair).action_confirm()
        with self.assertRaises(UserError):
            meeting.with_user(self.member).write({"decisions": "<p>rewritten</p>"})

    def test_action_items_stay_editable_after_confirmation(self):
        """Following up is the point, so the actions are not frozen."""
        meeting = self._meeting()
        action = self._action(meeting)
        meeting.with_user(self.chair).action_confirm()
        action.with_user(self.chair).write({"date_deadline": "2030-06-01"})
        self.assertEqual(str(action.date_deadline), "2030-06-01")

    def test_an_approver_can_reopen_and_it_is_logged(self):
        meeting = self._meeting()
        meeting.with_user(self.chair).action_confirm()
        before = len(meeting.message_ids)
        meeting.with_user(self.chair).action_reopen()
        self.assertEqual(meeting.state, "draft")
        self.assertGreater(len(meeting.message_ids), before)

    def test_a_non_approver_cannot_reopen(self):
        meeting = self._meeting()
        meeting.with_user(self.chair).action_confirm()
        with self.assertRaises(UserError):
            meeting.with_user(self.member).action_reopen()

    def test_a_milestone_from_another_project_is_refused(self):
        other = self.env["project.project"].create(
            {"name": "Other project", "allow_milestones": True})
        milestone = self.env["project.milestone"].create(
            {"name": "Foreign gate", "project_id": other.id})
        with self.assertRaises(ValidationError):
            self._meeting(milestone_id=milestone.id)

    def test_action_counts_track_their_states(self):
        meeting = self._meeting()
        a1 = self._action(meeting, name="One")
        self._action(meeting, name="Two")
        self.assertEqual(meeting.action_count, 2)
        self.assertEqual(meeting.action_open_count, 2)

        a1.with_user(self.chair).action_approve()
        a1.with_user(self.chair).action_create_task()
        meeting.invalidate_recordset()
        self.assertEqual(meeting.action_converted_count, 1)
        self.assertEqual(meeting.action_open_count, 1)

    # ── visibility ──────────────────────────────────────────────────────
    def test_an_unrelated_user_cannot_see_the_minutes(self):
        outsider = self.env["res.users"].create({
            "name": "Outsider", "login": "outsider.mom@example.com",
            "groups_id": [(6, 0, [self.user_group.id])],
        })
        meeting = self._meeting()
        visible = self.Meeting.with_user(outsider).search(
            [("id", "=", meeting.id)])
        self.assertFalse(visible,
                         "minutes carry commercial and personnel discussion; "
                         "they are not visible to every project user")

    def test_an_attendee_can_see_the_minutes(self):
        meeting = self._meeting()
        visible = self.Meeting.with_user(self.member).search(
            [("id", "=", meeting.id)])
        self.assertEqual(visible, meeting)

    def test_the_responsible_user_can_see_their_action(self):
        meeting = self._meeting()
        action = self._action(meeting)
        visible = self.Action.with_user(self.member).search(
            [("id", "=", action.id)])
        self.assertEqual(visible, action)
