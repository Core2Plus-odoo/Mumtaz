"""Agent 4 — overdue posted customer invoices.

Built on ``AccountTestInvoicingCommon`` rather than the shared fixture: it is
still a ``TransactionCase`` underneath, but creating a postable invoice needs a
company with a chart of accounts, and standing that up by hand is how invoice
tests become flaky.

Note there is no summary constant to assert against. Production embeds the
overdue day count in the summary, so it changes daily — which is precisely why
the agent dedupes on "has any activity" instead of on a marker string.
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestInvoiceChaser(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("c2p_agents.dry_run", "False")
        cls.call_type = cls.env.ref("mail.mail_activity_data_call")
        cls.todo_type = cls.env.ref("mail.mail_activity_data_todo")
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
        """Any Call this agent raised — matched by type, not by summary."""
        return self.env["mail.activity"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("activity_type_id", "=", self.call_type.id),
                ("summary", "like", "Overdue%"),
            ]
        )

    def test_overdue_posted_invoice_is_chased_on_its_owner(self):
        invoice = self._invoice(due_days_ago=15)

        self.env["account.move"]._cron_chase_overdue_invoices()

        activity = self.chaser_activities(invoice)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.owner)

    def test_summary_carries_the_overdue_day_count(self):
        invoice = self._invoice(due_days_ago=15)

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertEqual(
            self.chaser_activities(invoice).summary,
            "Overdue 15 days - %s" % invoice.name,
        )

    def test_invoice_due_today_is_not_yet_overdue(self):
        invoice = self._invoice(due_days_ago=0)

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertFalse(self.chaser_activities(invoice))

    def test_draft_invoice_is_out_of_scope(self):
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

    def test_any_existing_activity_suppresses_the_chase(self):
        """Production's dedupe, and the reason a summary marker would not work.

        An unrelated To-Do is enough to stop the call being raised. That is the
        original behaviour, and reproducing it matters: the alternative would
        have this agent pile a call on top of whatever a colleague scheduled.
        """
        invoice = self._invoice(due_days_ago=15)
        invoice.activity_schedule(
            activity_type_id=self.todo_type.id,
            summary="Somebody else's note",
            user_id=self.owner.id,
        )

        self.env["account.move"]._cron_chase_overdue_invoices()

        self.assertFalse(self.chaser_activities(invoice))

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
