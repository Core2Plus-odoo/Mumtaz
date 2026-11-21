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

        cls.alice = cls.env["res.users"].create({
            "name": "Alice Delivery",
            "login": "alice.workhub@example.com",
            "groups_id": [(6, 0, [cls.env.ref("project.group_project_user").id])],
        })
        cls.bob = cls.env["res.users"].create({
            "name": "Bob Delivery",
            "login": "bob.workhub@example.com",
            "groups_id": [(6, 0, [cls.env.ref("project.group_project_user").id])],
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

    def test_my_projects_counts_open_work(self):
        self._task("One", self.alice)
        self._task("Two", self.alice)
        data = self.Hub.with_user(self.alice).get_data()
        rows = {r["id"]: r for r in data["my_projects"]}
        self.assertIn(self.project.id, rows)
        self.assertGreaterEqual(rows[self.project.id]["open_tasks"], 2)
