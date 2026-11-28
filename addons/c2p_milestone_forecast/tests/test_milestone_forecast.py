from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.c2p_milestone_forecast.models.project_milestone import (
    skip_change_reason,
)

COMMIT = date(2027, 3, 10)


@tagged("post_install", "-at_install")
class TestMilestoneForecast(TransactionCase):
    """Fictional data only. Everything runs as an ordinary project manager,
    because the superuser is exempt from the reason rule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "TEST Delivery Owner", "login": "test-delivery-owner",
                "group_ids": [(6, 0, [
                    cls.env.ref("base.group_user").id,
                    cls.env.ref("project.group_project_manager").id])]})
        cls.project = cls.env["project.project"].create({
            "name": "TEST Forecast Project", "allow_milestones": True,
            "privacy_visibility": "employees"})
        cls.Milestone = cls.env["project.milestone"].with_user(cls.user)

    def _milestone(self, late=None, name="TEST M1", **vals):
        base = {"name": name, "project_id": self.project.id, "deadline": COMMIT}
        if late is not None:
            base["c2p_forecast_date"] = COMMIT + timedelta(days=late)
        base.update(vals)
        return self.Milestone.create(base)

    def _flush_tracking(self):
        """Tracking messages are written just before commit. A test never
        commits, so run that step by hand: once after creating the record, so
        the change under test is not folded into its creation, and once after
        the change."""
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _last_tracking_message(self, ms):
        return self.env["mail.message"].search(
            [("model", "=", "project.milestone"), ("res_id", "=", ms.id),
             ("tracking_value_ids", "!=", False)], order="id desc", limit=1)

    # ── colour boundaries ────────────────────────────────────────────────
    def test_boundaries(self):
        for late, colour in ((-3, "green"), (0, "green"), (1, "amber"),
                             (5, "amber"), (6, "red"), (40, "red")):
            with self.subTest(days_late=late):
                ms = self._milestone(late=late, name=f"TEST {late}")
                self.assertEqual(ms.c2p_health, colour)

    def test_no_forecast_is_grey_never_green(self):
        ms = self._milestone()
        self.assertEqual(ms.c2p_health, "grey")
        self.assertEqual(
            dict(ms._fields["c2p_health"].selection)["grey"], "No forecast")

    def test_forecast_without_commitment_is_grey(self):
        ms = self._milestone(deadline=False,
                             c2p_forecast_date=COMMIT)
        self.assertEqual(ms.c2p_health, "grey")

    def test_health_follows_each_change(self):
        ms = self._milestone(late=0)
        ms.write({"c2p_forecast_date": COMMIT + timedelta(days=5),
                  "c2p_change_reason": "TEST data late"})
        self.assertEqual(ms.c2p_health, "amber")
        ms.write({"c2p_forecast_date": COMMIT + timedelta(days=6),
                  "c2p_change_reason": "TEST data later still"})
        self.assertEqual(ms.c2p_health, "red")
        self.assertEqual(ms.c2p_days_late, 6)
        # Moving the commitment out brings it back.
        ms.write({"deadline": COMMIT + timedelta(days=6),
                  "c2p_change_reason": "TEST commitment renegotiated"})
        self.assertEqual(ms.c2p_health, "green")

    def test_health_cannot_be_set_by_hand(self):
        ms = self._milestone(late=6)
        with self.assertRaises(UserError):
            ms.write({"c2p_health": "green"})
        created = self._milestone(late=6, name="TEST typed", c2p_health="green")
        self.assertEqual(created.c2p_health, "red")

    # ── roll-up ──────────────────────────────────────────────────────────
    def test_project_shows_its_worst_milestone(self):
        self.assertEqual(self.project.c2p_milestone_health, "grey")
        self._milestone(name="TEST no forecast")
        self.assertEqual(self.project.c2p_milestone_health, "grey")
        self._milestone(late=0, name="TEST green")
        self.assertEqual(self.project.c2p_milestone_health, "green")
        amber = self._milestone(late=3, name="TEST amber")
        self.assertEqual(self.project.c2p_milestone_health, "amber")
        self._milestone(late=9, name="TEST red")
        self.assertEqual(self.project.c2p_milestone_health, "red")
        self.assertEqual(amber.c2p_health, "amber")

    def test_grey_does_not_hide_a_green_project(self):
        self._milestone(late=0, name="TEST green")
        self._milestone(name="TEST no forecast")
        self.assertEqual(self.project.c2p_milestone_health, "green")

    # ── reason required ──────────────────────────────────────────────────
    def test_changing_a_forecast_needs_a_reason(self):
        ms = self._milestone(late=0)
        for reason in (None, "", "   "):
            with self.subTest(reason=reason), self.assertRaises(UserError):
                vals = {"c2p_forecast_date": COMMIT + timedelta(days=2)}
                if reason is not None:
                    vals["c2p_change_reason"] = reason
                ms.write(vals)
        self.assertEqual(ms.c2p_forecast_date, COMMIT)

    def test_changing_a_commitment_needs_a_reason(self):
        ms = self._milestone(late=0)
        with self.assertRaises(UserError):
            ms.write({"deadline": COMMIT + timedelta(days=7)})
        with self.assertRaises(UserError):
            ms.write({"deadline": False})
        self.assertEqual(ms.deadline, COMMIT)

    def test_first_entry_and_unrelated_edits_need_no_reason(self):
        ms = self._milestone(deadline=False)
        ms.write({"deadline": COMMIT})
        ms.write({"c2p_forecast_date": COMMIT})
        ms.write({"name": "TEST renamed"})
        ms.write({"deadline": COMMIT, "c2p_forecast_date": COMMIT})
        self.assertEqual(ms.c2p_health, "green")

    def test_reason_is_stored_with_the_tracked_change(self):
        ms = self._milestone(late=0)
        self._flush_tracking()
        ms.write({"c2p_forecast_date": COMMIT + timedelta(days=4),
                  "c2p_change_reason": "TEST <b>client</b> data arrived late"})
        self._flush_tracking()
        message = self._last_tracking_message(ms)
        self.assertTrue(message, "no tracking message was posted")
        tracked = message.tracking_value_ids.mapped("field_id.name")
        self.assertIn("c2p_forecast_date", tracked)
        self.assertIn("client", message.body)
        self.assertIn("data arrived late", message.body)
        # What was typed is text, not markup.
        self.assertNotIn("<b>client</b>", message.body)

    def test_commitment_change_keeps_the_old_value_in_history(self):
        ms = self._milestone(late=0)
        self._flush_tracking()
        ms.write({"deadline": COMMIT + timedelta(days=14),
                  "c2p_change_reason": "TEST scope extended by agreement"})
        self._flush_tracking()
        message = self._last_tracking_message(ms)
        value = message.tracking_value_ids.filtered(
            lambda v: v.field_id.name == "deadline")
        self.assertEqual(value.old_value_datetime.date(), COMMIT)
        self.assertEqual(value.new_value_datetime.date(),
                         COMMIT + timedelta(days=14))
        self.assertIn("scope extended", message.body)

    def test_reason_is_not_kept_or_reused(self):
        ms = self._milestone(late=0)
        ms.write({"c2p_forecast_date": COMMIT + timedelta(days=1),
                  "c2p_change_reason": "TEST first reason"})
        self.assertFalse(ms.c2p_change_reason)
        self.assertNotIn("c2p_change_reason",
                         [c for c in self._columns("project_milestone")])
        with self.assertRaises(UserError):
            ms.write({"c2p_forecast_date": COMMIT + timedelta(days=2)})

    def _columns(self, table):
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s", (table,))
        return [row[0] for row in self.env.cr.fetchall()]

    def test_documented_bypass(self):
        """Trusted code in this process can skip the reason; sudo too."""
        ms = self._milestone(late=0)
        with skip_change_reason():
            ms.write({"c2p_forecast_date": COMMIT + timedelta(days=8)})
        self.assertEqual(ms.c2p_health, "red")
        ms.sudo().write({"c2p_forecast_date": COMMIT})
        self.assertEqual(ms.c2p_health, "green")

    def test_the_skip_does_not_outlive_its_block(self):
        ms = self._milestone(late=0)
        with skip_change_reason():
            pass
        with self.assertRaises(UserError):
            ms.write({"c2p_forecast_date": COMMIT + timedelta(days=2)})

    # ── keys an API caller can send are not bypasses ─────────────────────
    def test_context_keys_do_not_skip_the_reason(self):
        """A context is chosen by the caller, so it must not switch the rule
        off: every key the old code honoured is refused now."""
        for key in ("c2p_skip_change_reason", "install_mode", "module",
                    "c2p_forecast_internal"):
            with self.subTest(key=key):
                ms = self._milestone(late=0, name="TEST %s" % key)
                with self.assertRaises(UserError):
                    ms.with_context(**{key: True}).write(
                        {"deadline": COMMIT + timedelta(days=3)})
                self.assertEqual(ms.deadline, COMMIT)

    def test_context_cannot_set_the_health_by_hand(self):
        ms = self._milestone(late=0)
        with self.assertRaises(UserError):
            ms.with_context(c2p_forecast_internal=True).write(
                {"c2p_health": "red"})
        self.assertEqual(ms.c2p_health, "green")

    def test_context_cannot_create_a_milestone_with_a_chosen_health(self):
        ms = self.Milestone.with_context(c2p_forecast_internal=True).create({
            "name": "TEST forged", "project_id": self.project.id,
            "deadline": COMMIT, "c2p_forecast_date": COMMIT,
            "c2p_health": "red"})
        self.assertEqual(ms.c2p_health, "green")

    # ── reached milestones ───────────────────────────────────────────────
    def test_reached_milestone_keeps_its_colour(self):
        ms = self._milestone(late=3)
        self.assertEqual(ms.c2p_health, "amber")
        ms.write({"is_reached": True})
        self.assertEqual(ms.c2p_health, "amber")
        ms.write({"c2p_forecast_date": COMMIT + timedelta(days=30),
                  "c2p_change_reason": "TEST late paperwork"})
        self.assertEqual(ms.c2p_health, "amber")
        ms.write({"deadline": COMMIT + timedelta(days=60),
                  "c2p_change_reason": "TEST tidy-up"})
        self.assertEqual(ms.c2p_health, "amber")
        self.assertEqual(self.project.c2p_milestone_health, "amber")

    def test_colour_is_taken_at_the_moment_of_reaching(self):
        ms = self._milestone(late=0)
        ms.write({"is_reached": True,
                  "c2p_forecast_date": COMMIT + timedelta(days=9),
                  "c2p_change_reason": "TEST reached late"})
        self.assertEqual(ms.c2p_health, "red")

    def test_reopened_milestone_is_recalculated(self):
        ms = self._milestone(late=3)
        ms.write({"is_reached": True})
        ms.write({"c2p_forecast_date": COMMIT + timedelta(days=30),
                  "c2p_change_reason": "TEST"})
        ms.write({"is_reached": False})
        self.assertEqual(ms.c2p_health, "red")
