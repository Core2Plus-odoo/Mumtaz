"""Shared fixtures for the agent tests.

Every test here asserts on *its own* records rather than on the counts an agent
returns. A test database may carry demo data that legitimately matches an
agent's domain, and assertions like "acted == 1" would then pass or fail
depending on what else is installed.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class C2pAgentsCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Tests exercise the live path by default; the dry-run tests pass
        # dry_run=True explicitly. Set on the parameter rather than per call so
        # a test that forgets to pass it still runs against a known state.
        cls.env["ir.config_parameter"].sudo().set_param("c2p_agents.dry_run", "False")

        cls.salesperson = cls.env["res.users"].create(
            {
                "name": "C2P Agent Test Salesperson",
                "login": "c2p_agent_test_salesperson",
                # v19: the field is group_ids. groups_id was removed.
                "group_ids": [
                    (6, 0, [cls.env.ref("sales_team.group_sale_salesman").id])
                ],
            }
        )

        cls.todo_type = cls.env.ref("mail.mail_activity_data_todo")
        cls.call_type = cls.env.ref("mail.mail_activity_data_call")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def age(self, records, field_name, days):
        """Backdate a stored, ORM-maintained field so a time domain selects it.

        Raw SQL because `write_date` and `date_last_stage_update` are written by
        the ORM itself and cannot be set through `write()`. Confined to tests;
        the table and column names come from the registry, not from input.
        """
        self.assertIn(field_name, records._fields)
        when = fields.Datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            "UPDATE %s SET %s = %%s WHERE id IN %%s"
            % (records._table, field_name),
            (when, tuple(records.ids)),
        )
        records.invalidate_recordset([field_name])

    def agent_activities(self, record, activity_type, summary):
        """Activities this module would consider a duplicate marker on `record`."""
        return self.env["mail.activity"].search(
            [
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
                ("activity_type_id", "=", activity_type.id),
                ("summary", "=", summary),
            ]
        )

    def make_lead(self, **values):
        values.setdefault("name", "Test Lead")
        values.setdefault("type", "opportunity")
        values.setdefault("user_id", self.salesperson.id)
        return self.env["crm.lead"].create(values)
