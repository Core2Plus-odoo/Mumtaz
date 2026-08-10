"""The health column over ir.cron — chiefly, does it catch an empty body.

This is the diagnostic that would have caught the original failure, so the test
that matters most is the one asserting an empty `code` field reads as `empty`
rather than as a healthy scheduled action.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestAgentHealth(C2pAgentsCommon):
    def _cron(self, **values):
        values.setdefault("name", "Test cron")
        values.setdefault("model_id", self.env.ref("crm.model_crm_lead").id)
        values.setdefault("state", "code")
        values.setdefault("code", "model._cron_score_leads()")
        values.setdefault("interval_number", 1)
        values.setdefault("interval_type", "days")
        return self.env["ir.cron"].create(values)

    def test_empty_code_is_flagged(self):
        """The original failure: scheduled, active, running, doing nothing."""
        cron = self._cron(name="Silently empty", code="")
        cron.lastcall = fields.Datetime.now()

        self.assertEqual(cron.c2p_health, "empty")
        self.assertEqual(cron.c2p_code_length, 0)

    def test_whitespace_only_code_is_also_empty(self):
        """A body of blank lines runs and does nothing just as effectively."""
        cron = self._cron(name="Just whitespace", code="   \n\n  \t ")
        cron.lastcall = fields.Datetime.now()

        self.assertEqual(cron.c2p_health, "empty")

    def test_healthy_cron_reads_ok(self):
        cron = self._cron(name="Working fine")
        cron.lastcall = fields.Datetime.now()
        cron.nextcall = fields.Datetime.now() + timedelta(hours=12)

        self.assertEqual(cron.c2p_health, "ok")
        self.assertGreater(cron.c2p_code_length, 0)

    def test_never_run_cron_is_flagged(self):
        cron = self._cron(name="Never fired")
        cron.lastcall = False

        self.assertEqual(cron.c2p_health, "never_ran")

    def test_overdue_cron_is_flagged(self):
        cron = self._cron(name="Stuck")
        cron.lastcall = fields.Datetime.now() - timedelta(days=3)
        cron.nextcall = fields.Datetime.now() - timedelta(days=2)

        self.assertEqual(cron.c2p_health, "overdue")

    def test_a_slightly_late_cron_is_not_overdue(self):
        """Minutes of drift is a busy worker, not a fault."""
        cron = self._cron(name="Slightly late")
        cron.lastcall = fields.Datetime.now() - timedelta(hours=25)
        cron.nextcall = fields.Datetime.now() - timedelta(minutes=20)

        self.assertEqual(cron.c2p_health, "ok")

    def test_inactive_outranks_everything_but_is_still_visible(self):
        """An archived cron reads as inactive, not as a false alarm."""
        cron = self._cron(name="Switched off", code="")
        cron.active = False

        self.assertEqual(cron.c2p_health, "inactive")

    def test_empty_outranks_never_ran(self):
        """Worst-first: a blank body is the more useful thing to be told."""
        cron = self._cron(name="Empty and unfired", code="")
        cron.lastcall = False

        self.assertEqual(cron.c2p_health, "empty")

    def test_this_modules_own_crons_are_healthy(self):
        """A guard against shipping the very thing this module was written for."""
        ours = self.env["ir.cron"].with_context(active_test=False).search(
            [("name", "ilike", "C2P Agent")]
        )
        self.assertEqual(len(ours), 7, "all seven agents should be installed")
        for cron in ours:
            self.assertNotEqual(
                cron.c2p_health, "empty", "%s has an empty body" % cron.name
            )
            self.assertGreater(cron.c2p_code_length, 0)
