import base64

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c6360000002000001e221bc330000000049454e44ae426082"
))


@tagged("post_install", "-at_install", "faizy")
class TestEvidenceRoute(HttpCase):
    """A customer gets an evidence image only after approval, and only for their own order."""

    def setUp(self):
        super().setUp()
        mk = lambda login, groups: mail_new_test_user(self.env, login=login, name=login, groups=groups)
        self.ops = mk("route_ops", "faizy_core.group_faizy_ops")
        self.cust_a = mk("route_cust_a", "base.group_portal")
        self.cust_b = mk("route_cust_b", "base.group_portal")
        service = self.env["faizy.service"].search([], limit=1) or self.env["faizy.service"].create(
            {"name": "Route test service"})
        self.order = self.env["faizy.order"].create({
            "title": "SYNTHETIC route order", "partner_id": self.cust_a.partner_id.id,
            "service_id": service.id, "city": "Karachi", "state": "in_progress",
            "proof_image": PNG,
        })

    def _status(self, path):
        return self.url_open(path).status_code

    def test_customer_route(self):
        url = "/faizy/evidence/%s/proof" % self.order.id
        self.authenticate("route_cust_a", "route_cust_a")
        self.assertEqual(self._status(url), 404, "unreviewed evidence must not be served")
        self.order.with_user(self.ops).action_approve_evidence()
        self.assertEqual(self._status(url), 200, "approved evidence is served to its owner")
        self.assertEqual(self._status("/faizy/evidence/%s/receipt" % self.order.id), 404, "no receipt exists")
        self.assertEqual(self._status("/faizy/evidence/%s/other" % self.order.id), 404)
        # The raw field URL may answer 200 with Odoo's generic placeholder, so
        # compare the bytes: the customer must never receive the stored image.
        raw = self.url_open("/web/image/faizy.order/%s/proof_image" % self.order.id)
        self.assertNotEqual(raw.content, base64.b64decode(PNG),
                            "the raw field URL must not return the stored image")
        served = self.url_open(url)
        self.assertEqual(served.content, base64.b64decode(PNG), "the route returns the stored image")

    def test_other_customer_gets_404(self):
        self.order.with_user(self.ops).action_approve_evidence()
        self.authenticate("route_cust_b", "route_cust_b")
        self.assertEqual(self._status("/faizy/evidence/%s/proof" % self.order.id), 404)
