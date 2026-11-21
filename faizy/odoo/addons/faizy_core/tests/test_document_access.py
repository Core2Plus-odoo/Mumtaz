from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "faizy")
class TestDocumentAccess(TransactionCase):
    """The document vault holds identity documents.

    A portal customer has read access to the model, so the record rule is the
    only thing between one family's passport scan and every other customer.
    These tests fail if that rule is removed or loosened.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer_a = mail_new_test_user(
            cls.env, login="faizy_portal_a", name="Customer A", groups="base.group_portal"
        )
        cls.customer_b = mail_new_test_user(
            cls.env, login="faizy_portal_b", name="Customer B", groups="base.group_portal"
        )
        Document = cls.env["faizy.document"]
        cls.doc_a = Document.create(
            {"name": "Passport A", "doc_type": "passport", "partner_id": cls.customer_a.partner_id.id}
        )
        cls.doc_b = Document.create(
            {"name": "CNIC B", "doc_type": "cnic", "partner_id": cls.customer_b.partner_id.id}
        )

    def test_customer_search_returns_only_own_documents(self):
        found = self.env["faizy.document"].with_user(self.customer_a).search([])
        self.assertEqual(found, self.doc_a)

    def test_customer_can_read_own_document(self):
        doc = self.doc_a.with_user(self.customer_a)
        self.assertEqual(doc.name, "Passport A")

    def test_customer_cannot_read_another_customers_document(self):
        with self.assertRaises(AccessError):
            self.doc_b.with_user(self.customer_a).read(["name"])

    def test_customer_cannot_read_another_customers_file(self):
        with self.assertRaises(AccessError):
            self.doc_b.with_user(self.customer_a).read(["attachment"])

    def test_customer_cannot_write_own_document(self):
        # The portal ACL is read-only; the rule must not have widened it.
        with self.assertRaises(AccessError):
            self.doc_a.with_user(self.customer_a).write({"name": "changed"})

    def test_operations_still_sees_every_document(self):
        ops = mail_new_test_user(
            self.env, login="faizy_ops_user", name="Ops", groups="faizy_core.group_faizy_ops"
        )
        found = self.env["faizy.document"].with_user(ops).search(
            [("id", "in", (self.doc_a | self.doc_b).ids)]
        )
        self.assertEqual(found, self.doc_a | self.doc_b)
