from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestWorkHub(TransactionCase):
    """The hub reads one user's work and writes one deliberate update.

    Two things these tests exist to pin, because both are easy to regress:
    a personal work list must not leak another user's tasks, and a quick
    update must record freshness without becoming indistinguishable from an
    incidental write.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Task = cls.env["project.task"]
        cls.Hub = cls.env["c2p.work.hub"]

        # Odoo 19 renamed res.users.groups_id to group_ids; resolve it rather
        # than hardcode either spelling.
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.group_field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        cls.alice = Users.create({
            "name": "Alice Delivery",
            "login": "alice.workhub@example.com",
            cls.group_field: [(6, 0, [cls.env.ref("project.group_project_user").id])],
        })
        cls.bob = Users.create({
            "name": "Bob Delivery",
            "login": "bob.workhub@example.com",
            cls.group_field: [(6, 0, [cls.env.ref("project.group_project_user").id])],
        })

        cls.project = cls.env["project.project"].create({"name": "Hub Test Project"})
        # Stage names are what the hub matches on, so they must read like real
        # ones rather than being contrived.
        cls.stage_todo, cls.stage_waiting, cls.stage_review = \
            cls.env["project.task.type"].create([
                {"name": "To Do", "sequence": 1,
                 "project_ids": [(6, 0, [cls.project.id])]},
                {"name": "Waiting on Client", "sequence": 2,
                 "project_ids": [(6, 0, [cls.project.id])]},
                {"name": "In Review", "sequence": 3,
                 "project_ids": [(6, 0, [cls.project.id])]},
            ])

    def _task(self, name, user, **vals):
        base = {
            "name": name,
            "project_id": self.project.id,
            "user_ids": [(6, 0, [user.id])],
            "stage_id": self.stage_todo.id,
        }
        base.update(vals)
        return self.Task.create(base)

    # ── the quick update ────────────────────────────────────────────────
    def test_quick_update_records_freshness_and_chatter(self):
        task = self._task("Write the spec", self.alice)
        self.assertFalse(task.c2p_last_update)
        before = len(task.message_ids)

        task.with_user(self.alice).action_c2p_quick_update({
            "progress": "Drafted sections 1-3",
            "next_action": "Review with the client",
        })

        task.invalidate_recordset()
        self.assertTrue(task.c2p_last_update, "a deliberate update must stamp freshness")
        self.assertEqual(task.c2p_next_action, "Review with the client")
        self.assertGreater(len(task.message_ids), before,
                           "the update must leave a chatter trail")

    def test_quick_update_rejects_an_empty_payload(self):
        task = self._task("Nothing to say", self.alice)
        with self.assertRaises(UserError):
            task.with_user(self.alice).action_c2p_quick_update({})
        with self.assertRaises(UserError):
            task.with_user(self.alice).action_c2p_quick_update(
                {"progress": "   ", "next_action": ""})

    def test_quick_update_rejects_an_unknown_state(self):
        task = self._task("Bad status", self.alice)
        with self.assertRaises(UserError):
            task.with_user(self.alice).action_c2p_quick_update(
                {"state": "99_not_a_state"})

    def test_update_text_is_escaped_into_chatter(self):
        """Progress, blocker and next-action text comes from a user, so it must
        reach chatter escaped. The first draft of this module interpolated it
        straight into HTML."""
        task = self._task("Escaping check", self.alice)
        evil = "<script>alert(1)</script>"
        task.with_user(self.alice).action_c2p_quick_update(
            {"progress": evil, "next_action": evil, "blocker": evil})

        body = task.message_ids[0].body or ""
        self.assertNotIn("<script>", body,
                         "user text must never reach chatter as live markup")
        self.assertIn("&lt;script&gt;", body,
                      "the text itself must still be readable, just escaped")

    def test_an_incidental_write_does_not_fake_freshness(self):
        """write_date moves for any change; c2p_last_update must not."""
        task = self._task("Renamed, not updated", self.alice)
        task.write({"name": "Renamed again"})
        task.invalidate_recordset()
        self.assertFalse(task.c2p_last_update)

    def test_blocker_moves_the_task_to_the_waiting_stage(self):
        task = self._task("Needs client data", self.alice)
        task.with_user(self.alice).action_c2p_quick_update(
            {"blocker": "Waiting for the trial balance"})
        task.invalidate_recordset()
        self.assertEqual(task.stage_id, self.stage_waiting)

    def test_blocker_is_recorded_even_with_no_waiting_stage(self):
        """A project configured without a waiting stage must still accept the
        update — losing a blocker because of configuration would be worse than
        leaving the stage alone."""
        other = self.env["project.project"].create({"name": "No Waiting Stage"})
        stage = self.env["project.task.type"].create(
            {"name": "Open", "sequence": 1, "project_ids": [(6, 0, [other.id])]})
        task = self.Task.create({
            "name": "Blocked somewhere else",
            "project_id": other.id,
            "stage_id": stage.id,
            "user_ids": [(6, 0, [self.alice.id])],
        })
        task.with_user(self.alice).action_c2p_quick_update({"blocker": "Vendor silent"})
        task.invalidate_recordset()
        self.assertEqual(task.stage_id, stage, "stage must be left as it was")
        self.assertTrue(task.c2p_last_update, "the update itself must still land")

    def test_blocker_field_is_reused_not_duplicated(self):
        """When c2p_project_tracker is installed the hub writes its field; when
        it is not, the hub declares no replacement."""
        blocker_field = self.Task._c2p_blocker_field()
        if blocker_field:
            task = self._task("Reuse check", self.alice)
            task.with_user(self.alice).action_c2p_quick_update({"blocker": "Vendor silent"})
            task.invalidate_recordset()
            self.assertEqual(task[blocker_field], "Vendor silent")
        else:
            self.assertNotIn("c2p_blocked_reason", self.Task._fields,
                             "the hub must not add a second blocker field")

    # ── submit for review ───────────────────────────────────────────────
    def test_submit_for_review_moves_to_the_review_stage(self):
        task = self._task("Ready", self.alice)
        task.with_user(self.alice).action_c2p_submit_for_review()
        task.invalidate_recordset()
        self.assertEqual(task.stage_id, self.stage_review)
        self.assertTrue(task.c2p_last_update)

    def test_submit_for_review_explains_a_missing_stage(self):
        other = self.env["project.project"].create({"name": "No Review Stage"})
        stage = self.env["project.task.type"].create(
            {"name": "Open", "sequence": 1, "project_ids": [(6, 0, [other.id])]})
        task = self.Task.create({
            "name": "Nowhere to go", "project_id": other.id,
            "stage_id": stage.id, "user_ids": [(6, 0, [self.alice.id])]})
        with self.assertRaises(UserError):
            task.with_user(self.alice).action_c2p_submit_for_review()

    # ── the payload ─────────────────────────────────────────────────────
    def test_payload_shows_only_my_own_work(self):
        mine = self._task("Mine", self.alice)
        theirs = self._task("Theirs", self.bob)

        data = self.Hub.with_user(self.alice).get_data()
        ids = {t["id"] for section in data.values()
               if isinstance(section, dict) and "tasks" in section
               for t in section["tasks"]}
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids,
                         "a personal work list must never show another user's task")

    def test_overdue_and_today_are_separated(self):
        from datetime import date, timedelta
        today = date.today()
        late = self._task("Late", self.alice,
                          date_deadline=today - timedelta(days=2))
        due = self._task("Due now", self.alice, date_deadline=today)

        data = self.Hub.with_user(self.alice).get_data()
        self.assertIn(late.id, [t["id"] for t in data["overdue"]["tasks"]])
        self.assertIn(due.id, [t["id"] for t in data["today"]["tasks"]])
        self.assertNotIn(due.id, [t["id"] for t in data["overdue"]["tasks"]])

    def test_a_task_with_no_update_counts_as_stale(self):
        task = self._task("Never updated", self.alice)
        data = self.Hub.with_user(self.alice).get_data()
        self.assertIn(task.id, [t["id"] for t in data["stale"]["tasks"]])

        task.with_user(self.alice).action_c2p_quick_update({"progress": "Moving"})
        data = self.Hub.with_user(self.alice).get_data()
        self.assertNotIn(task.id, [t["id"] for t in data["stale"]["tasks"]],
                         "an updated task must leave the stale list")

    def test_closed_tasks_drop_out_of_every_section(self):
        task = self._task("Finishing", self.alice)
        closed = self.Task._c2p_closed_states()
        self.assertTrue(closed, "there must be at least one closed state")
        task.write({"state": closed[0]})

        data = self.Hub.with_user(self.alice).get_data()
        ids = {t["id"] for section in data.values()
               if isinstance(section, dict) and "tasks" in section
               for t in section["tasks"]}
        self.assertNotIn(task.id, ids)

    def test_closed_states_are_probed_not_hardcoded(self):
        closed = self.Task._c2p_closed_states()
        valid = {k for k, _l in self.Task._fields["state"].selection}
        self.assertTrue(set(closed) <= valid,
                        "every closed state must exist in this version's selection")

    def test_payload_carries_meta_and_state_choices(self):
        self._task("Something", self.alice)
        data = self.Hub.with_user(self.alice).get_data()
        self.assertEqual(data["meta"]["user_name"], self.alice.name)
        self.assertTrue(data["states"], "the update panel needs status choices")
        self.assertTrue(any(s["closed"] for s in data["states"]))

    def test_sections_expose_a_drill_down_domain(self):
        self._task("Drillable", self.alice)
        data = self.Hub.with_user(self.alice).get_data()
        for key, section in data.items():
            if isinstance(section, dict) and "tasks" in section:
                self.assertIn("action", section, f"{key} must be drillable")
                self.assertEqual(section["action"]["res_model"], "project.task")

    # ── manager review queue (Wave B) ───────────────────────────────────
    def test_review_queue_is_empty_for_a_non_manager(self):
        self._task("Not a manager's problem", self.alice)
        data = self.Hub.with_user(self.alice).get_data()
        self.assertFalse(data["waiting_for_me"]["is_manager"])
        self.assertEqual(data["waiting_for_me"]["count"], 0)

    def test_review_queue_shows_others_work_awaiting_me(self):
        managed = self.env["project.project"].create(
            {"name": "Alice Manages", "user_id": self.alice.id})
        review = self.env["project.task.type"].create(
            {"name": "In Review", "sequence": 1,
             "project_ids": [(6, 0, [managed.id])]})
        theirs = self.Task.create({
            "name": "Bob's work for review", "project_id": managed.id,
            "stage_id": review.id, "user_ids": [(6, 0, [self.bob.id])]})

        data = self.Hub.with_user(self.alice).get_data()
        queue = data["waiting_for_me"]
        self.assertTrue(queue["is_manager"])
        self.assertIn(theirs.id, [t["id"] for t in queue["tasks"]])

    def test_review_queue_excludes_my_own_tasks(self):
        """A manager's own work belongs in their work list, not their queue —
        otherwise every task they own is counted twice."""
        managed = self.env["project.project"].create(
            {"name": "Alice Manages Too", "user_id": self.alice.id})
        review = self.env["project.task.type"].create(
            {"name": "In Review", "sequence": 1,
             "project_ids": [(6, 0, [managed.id])]})
        own = self.Task.create({
            "name": "Alice's own task", "project_id": managed.id,
            "stage_id": review.id, "user_ids": [(6, 0, [self.alice.id])]})

        data = self.Hub.with_user(self.alice).get_data()
        self.assertNotIn(own.id,
                         [t["id"] for t in data["waiting_for_me"]["tasks"]])

    # ── blocked is not the same as waiting ──────────────────────────────
    def test_blocked_and_waiting_are_separate_sections(self):
        waiting = self._task("Sat with the client", self.alice,
                             stage_id=self.stage_waiting.id)
        data = self.Hub.with_user(self.alice).get_data()
        self.assertIn(waiting.id,
                      [t["id"] for t in data["waiting_on_others"]["tasks"]])

        blocker_field = self.Task._c2p_blocker_field()
        if blocker_field:
            # Waiting-on-Client needs a reason on a delivery project, so set it
            # on a plain To Do task to isolate the blocked section.
            blocked = self._task("Stuck", self.alice)
            blocked.write({blocker_field: "Vendor silent"})
            data = self.Hub.with_user(self.alice).get_data()
            self.assertIn(blocked.id,
                          [t["id"] for t in data["blocked"]["tasks"]])

    # ── upcoming milestones ─────────────────────────────────────────────
    def test_upcoming_milestones_use_the_standard_model(self):
        from datetime import date, timedelta
        self.project.write({"allow_milestones": True})
        self._task("Work on the project", self.alice)
        soon = self.env["project.milestone"].create({
            "name": "Design sign-off", "project_id": self.project.id,
            "deadline": date.today() + timedelta(days=5)})

        data = self.Hub.with_user(self.alice).get_data()
        rows = {m["id"]: m for m in data["my_milestones"]}
        self.assertIn(soon.id, rows)
        self.assertFalse(rows[soon.id]["overdue"])

    def test_a_late_milestone_is_flagged(self):
        from datetime import date, timedelta
        self.project.write({"allow_milestones": True})
        self._task("Work on the project", self.alice)
        late = self.env["project.milestone"].create({
            "name": "UAT gate", "project_id": self.project.id,
            "deadline": date.today() - timedelta(days=3)})

        data = self.Hub.with_user(self.alice).get_data()
        rows = {m["id"]: m for m in data["my_milestones"]}
        self.assertIn(late.id, rows)
        self.assertTrue(rows[late.id]["overdue"])

    def test_reached_and_distant_milestones_are_excluded(self):
        from datetime import date, timedelta
        self.project.write({"allow_milestones": True})
        self._task("Work on the project", self.alice)
        reached = self.env["project.milestone"].create({
            "name": "Already done", "project_id": self.project.id,
            "deadline": date.today() + timedelta(days=2), "is_reached": True})
        distant = self.env["project.milestone"].create({
            "name": "Far away", "project_id": self.project.id,
            "deadline": date.today() + timedelta(days=200)})

        data = self.Hub.with_user(self.alice).get_data()
        ids = [m["id"] for m in data["my_milestones"]]
        self.assertNotIn(reached.id, ids)
        self.assertNotIn(distant.id, ids)

    def test_my_projects_counts_open_work(self):
        self._task("One", self.alice)
        self._task("Two", self.alice)
        data = self.Hub.with_user(self.alice).get_data()
        rows = {r["id"]: r for r in data["my_projects"]}
        self.assertIn(self.project.id, rows)
        self.assertGreaterEqual(rows[self.project.id]["open_tasks"], 2)
