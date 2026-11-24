"""Shared fixture for the cross-company tests: two companies, one internal
user in each, the module's user group on both."""
from odoo.tests import TransactionCase


class TwoCompanyCase(TransactionCase):
    GROUPS = []

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company_a = env.company
        cls.company_b = env["res.company"].create({"name": "TEST Other Company"})
        Users = env["res.users"].with_context(no_reset_password=True)
        field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        groups = [env.ref("base.group_user").id] + [env.ref(g).id for g in cls.GROUPS]

        def make(login, company):
            return Users.create({"name": login, "login": login, field: [(6, 0, groups)],
                                 "company_id": company.id, "company_ids": [(6, 0, [company.id])]})
        cls.user_a = make(cls.LOGIN_PREFIX + "_a", cls.company_a)
        cls.user_b = make(cls.LOGIN_PREFIX + "_b", cls.company_b)

    def assertHiddenFromB(self, record):
        model = self.env[record._name]
        self.assertIn(record, model.with_user(self.user_a).search([("id", "=", record.id)]))
        self.assertFalse(model.with_user(self.user_b).search([("id", "=", record.id)]),
                         "%s must not be visible from another company" % record._name)
