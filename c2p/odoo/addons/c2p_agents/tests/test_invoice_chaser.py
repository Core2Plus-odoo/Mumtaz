"""Agent 4 — overdue posted customer invoices.

This one builds on ``AccountTestInvoicingCommon`` rather than the shared
``C2pAgentsCommon``. It is still a ``TransactionCase`` underneath, but creating
a postable invoice needs a company with a chart of accounts, and standing that
up by hand in a plain TransactionCase is how invoice tests become flaky.
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged

from ..models.account_move import CHASER_SUMMARY


@tagged("post_install", "-at_install")
class TestInvoiceChaser(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("c2p_agents.dry_run", "False")
        cls.call_type = cls.env.ref("mail.mail_activity_data_call")
        cls.owner = cls.env["res.users"].create(
            {
                "name": "C2P Invoice Owner",
                "login": "c2p_agent_test_invoice_owner",
                # v19: the field is group_ids, not groups_id.
                "group_ids": [
                    (6, 0, [cls.env.ref("account.group_account_invoice").id])
                ],
            }
        )

    def _invoice(self, due_days_ago, post=True, move_type="out_invoice"):
        """A customer invoice whose due date is `due_days_ago` days in the past."""
        today = fields.Date.context_today(self.env.user)
        invoice = self.init_invoice(
            move_type,
            partner=self.partner_a,
            invoice_date=today - timedelta(days=due_days_ago + 30),
            amounts=[1000.0],
        )
        # Clear the payment term first: leaving it in place would recompute the
        # due date from the invoice date and overwrite what the test just set.
        invoice.invoice_payment_term_id = False
        invoice.invoice_date_due = today - timedelta(days=due_days_ago)
        invoice.invoice_user_id = self.owner
        if post:
            invoice.action_post()
        return invoice

    def chaser_activities(self, move):
        return self.env["mail.activity"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("activity_type_id", "=", self.call_type.id),
                ("summary", "=", CHASER_SUMMARY),
            ]
        )

    def test_overdue_posted_invoice_is_chased_on_its_owner(self):
        invoice = self._invoice(due_days_ago=15)

        self.env["account.move"]._cron_chase_overdue_invoices()

        activity = self.chaser_activities(invoice)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.owner)

    def test_invoice_due_today_is_not_yet_overdue(self):
        invoice = self._invoice(due_days_ago=0)

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertFalse(self.chaser_activities(invoice))

    def test_draft_invoice_is_out_of_scope(self):
        """Nothing is owed on a draft, however old its due date looks."""
        invoice = self._invoice(due_days_ago=30, post=False)

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertFalse(self.chaser_activities(invoice))

    def test_paid_invoice_is_out_of_scope(self):
        invoice = self._invoice(due_days_ago=30)
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({})._create_payments()

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertEqual(invoice.payment_state, "paid", "sanity: it really is paid")
        self.assertFalse(self.chaser_activities(invoice))

    def test_vendor_bill_is_out_of_scope(self):
        bill = self._invoice(due_days_ago=30, move_type="in_invoice")

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertFalse(self.chaser_activities(bill))

    def test_existing_unrelated_activity_does_not_block_the_chase(self):
        """Unlike the CRM agents, this one chases regardless of other activities."""
        invoice = self._invoice(due_days_ago=15)
        invoice.activity_schedule(
            activity_type_id=self.env.ref("mail.mail_activity_data_todo").id,
            summary="Somebody else's note",
            user_id=self.owner.id,
        )

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertEqual(len(self.chaser_activities(invoice)), 1)

    def test_a_colleagues_copy_of_the_marker_still_counts(self):
        """Deduplication must see markers assigned to other users.

        This is the agent with no `activity_ids` filter, so it is the one where
        `_c2p_already_flagged` genuinely decides. If that search could not read
        another user's activities, this test would find two.
        """
        invoice = self._invoice(due_days_ago=15)
        other = self.env["res.users"].create(
            {
                "name": "C2P Other Collector",
                "login": "c2p_agent_test_other_collector",
                "group_ids": [
                    (6, 0, [self.env.ref("account.group_account_invoice").id])
                ],
            }
        )
        invoice.activity_schedule(
            activity_type_id=self.call_type.id,
            summary=CHASER_SUMMARY,
            user_id=other.id,
        )

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertEqual(len(self.chaser_activities(invoice)), 1)

    def test_an_already_flagged_invoice_is_scanned_but_not_acted_on(self):
        """It stays in the domain — only the marker stops a second activity."""
        invoice = self._invoice(due_days_ago=15)

        self.env["account.move"]._cron_chase_overdue_invoices()
        second = self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertIn(
            invoice,
            self.env["account.move"].search(
                self.env["account.move"]._c2p_overdue_domain(
                    fields.Date.context_today(self.env.user)
                )
            ),
        )
        self.assertGreaterEqual(second["scanned"], 1)
        self.assertEqual(len(self.chaser_activities(invoice)), 1)

    def test_rerun_does_not_duplicate(self):
        invoice = self._invoice(due_days_ago=15)

        self.env["account.move"]._cron_chase_overdue_invoices()
        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertEqual(len(self.chaser_activities(invoice)), 1)

    def test_dry_run_writes_nothing(self):
        invoice = self._invoice(due_days_ago=15)

        result = self.env["account.move"]._cron_chase_overdue_invoices(dry_run=True)

        self.assertGreaterEqual(result["acted"], 1, "it should still report intent")
        self.assertFalse(self.chaser_activities(invoice))
