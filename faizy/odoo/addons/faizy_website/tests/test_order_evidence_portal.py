import base64
import json

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests.common import HttpCase, tagged

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c6360000002000001e221bc330000000049454e44ae426082"
))


@tagged("post_install", "-at_install", "faizy")
class TestOrderEvidencePortal(HttpCase):
    """The customer's order page and JSON API show evidence only after review."""

    def setUp(self):
        super().setUp()

        def mk(login, groups):
            return mail_new_test_user(self.env, login=login, name=login, groups=groups)

        self.ops = mk("web_ops", "faizy_core.group_faizy_ops")
        self.cust = mk("web_cust", "base.group_portal")
        service = self.env["faizy.service"].search([], limit=1) or self.env["faizy.service"].create(
            {"name": "Portal evidence service"})
        self.order = self.env["faizy.order"].create({
            "title": "SYNTHETIC portal order", "partner_id": self.cust.partner_id.id,
            "service_id": service.id, "city": "Karachi", "state": "in_progress",
            "proof_image": PNG, "receipt_image": PNG, "purchase_value": 100,
        })
        self.authenticate("web_cust", "web_cust")

    def _page(self):
        return self.url_open("/care/orders/%s" % self.order.id)

    def _api(self):
        return self.url_open("/api/care/orders/%s" % self.order.id)

    def test_unreviewed_evidence_is_not_shown(self):
        page = self._page()
        self.assertEqual(page.status_code, 200, "the page must still render for the customer")
        self.assertNotIn("/faizy/evidence/", page.text)
        self.assertNotIn("/web/image/faizy.order/", page.text)
        api = self._api()
        self.assertEqual(api.status_code, 200)
        data = json.loads(api.text)
        self.assertIsNone(data["proof_image_url"])
        self.assertIsNone(data["receipt_image_url"])

    def test_approved_evidence_is_shown_through_the_reviewed_route(self):
        self.order.with_user(self.ops).action_approve_evidence()
        page = self._page()
        self.assertEqual(page.status_code, 200)
        self.assertIn("/faizy/evidence/%s/proof" % self.order.id, page.text)
        self.assertIn("/faizy/evidence/%s/receipt" % self.order.id, page.text)
        self.assertNotIn("/web/image/faizy.order/", page.text)
        data = json.loads(self._api().text)
        self.assertEqual(data["proof_image_url"], "/faizy/evidence/%s/proof" % self.order.id)
        self.assertEqual(data["receipt_image_url"], "/faizy/evidence/%s/receipt" % self.order.id)
