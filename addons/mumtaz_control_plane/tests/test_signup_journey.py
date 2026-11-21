import json
import os
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.mumtaz_tenant_manager.services.provisioning import ProvisionResult

ENV_FLAG = "MUMTAZ_REAL_PROVISIONING"
PUBLIC_FLAG = "mumtaz_control_plane.public_signup"


class _Common(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env.ref("mumtaz_control_plane.product_erp")
        cls.plan = cls.env.ref("mumtaz_control_plane.plan_erp_staging_trial")
        cls.Request = cls.env["mumtaz.signup.request"]
        cls.access = cls.env["mumtaz.feature.access.service"]

    def _request(self, name="Acme Trading LLC", email="owner@acme.example", **vals):
        return self.Request.create(dict({
            "name": name,
            "contact_name": "Amina Owner",
            "email": email,
            "product_id": self.product.id,
            "plan_id": self.plan.id,
        }, **vals))

    def _run_worker(self, result):
        """Run the provisioning queue with a provisioner that returns `result`
        (unit tests never create a database; scripts/tenant_journey_ci.sh does)."""
        class Stub:
            def run(self, tenant):
                return result

        with patch("odoo.addons.mumtaz_tenant_manager.services.provisioning.get_provisioner",
                   return_value=Stub()), patch.object(self.env.cr, "commit"):
            self.env["mumtaz.tenant"]._cron_run_provision_queue()


@tagged("post_install", "-at_install")
class TestSignupJourney(_Common):
    """Register organization → choose Mumtaz ERP → entitlement → staging
    tenant → workspace, with every gate on the way."""

    def test_catalogue_is_honest(self):
        Product = self.env["mumtaz.product"]
        self.assertEqual(self.product.status, "pilot")
        self.assertTrue(self.product.evidence)
        open_products = Product.search([("self_service", "=", True)])
        self.assertEqual(open_products, self.product,
                         "Only Mumtaz ERP is open to registration requests.")
        for code in ("zaki", "marketplace", "delivery_os"):
            self.assertEqual(Product.search([("code", "=", code)]).status, "planned")

    def test_planned_product_cannot_be_opened(self):
        zaki = self.env.ref("mumtaz_control_plane.product_zaki")
        with self.assertRaises(ValidationError):
            zaki.self_service = True

    def test_plan_must_belong_to_the_product(self):
        with self.assertRaises(ValidationError):
            self._request(product_id=self.env.ref("mumtaz_control_plane.product_jawhar").id)

    def test_approval_creates_organization_staging_tenant_and_entitlement(self):
        request = self._request()
        self.assertFalse(request.entitlement_granted)
        request.action_approve()

        self.assertEqual(request.state, "approved")
        partner = request.partner_id
        self.assertTrue(partner.is_company)
        self.assertEqual(partner.name, "Acme Trading LLC")
        self.assertEqual(partner.child_ids.name, "Amina Owner")

        tenant = request.tenant_id
        self.assertEqual(tenant.state, "draft", "Approval must not create or activate anything.")
        self.assertEqual(tenant.environment, "staging")
        self.assertEqual(tenant.code, "acme-trading-llc")
        self.assertEqual(tenant.database_name, "stg_acme_trading_llc")
        self.assertEqual(tenant.customer_partner_id, partner)
        self.assertEqual(tenant.admin_email, "owner@acme.example")
        self.assertEqual(tenant.bundle_id.code, "mumtaz_erp")

        subscription = request.subscription_id
        self.assertEqual(subscription.status, "trial")
        self.assertEqual(subscription.plan_id, self.plan)
        self.assertEqual((subscription.trial_end - subscription.trial_start).days, 14)

        # The entitlement is what the shared resolver says, not a flag on the request.
        self.assertTrue(self.access.resolve_feature_access_by_code(
            tenant, "erp_access")["effective_enabled"])
        self.assertTrue(self.access.resolve_feature_access_by_code(
            tenant, "erp_accounting")["effective_enabled"])
        self.assertFalse(self.access.resolve_feature_access_by_code(
            tenant, "zaki_access")["effective_enabled"])
        self.assertFalse(self.access.resolve_feature_access_by_code(
            tenant, "marketplace_access")["effective_enabled"])
        self.assertTrue(request.entitlement_granted)

    def test_tenant_codes_do_not_collide_or_take_reserved_names(self):
        first = self._request()
        first.action_approve()
        second = self._request(email="second@acme.example")
        second.action_approve()
        self.assertEqual(second.tenant_id.code, "acme-trading-llc-2")
        self.assertEqual(second.tenant_id.database_name, "stg_acme_trading_llc_2")
        reserved = self._request(name="ERP", email="x@erp.example")
        reserved.action_approve()
        self.assertEqual(reserved.tenant_id.code, "erp-org")
        arabic = self._request(name="شركة النور", email="x@alnoor.example")
        arabic.action_approve()
        self.assertTrue(arabic.tenant_id.code.startswith("org"))

    def test_plan_without_the_access_feature_cannot_be_approved(self):
        self.plan.plan_feature_ids.filtered(
            lambda line: line.feature_id.code == "erp_access").enabled = False
        request = self._request()
        with self.assertRaises(UserError):
            request.action_approve()

    def test_no_provisioning_before_approval(self):
        request = self._request()
        with self.assertRaises(UserError):
            request.action_provision()

    def test_no_provisioning_without_entitlement(self):
        request = self._request()
        request.action_approve()
        request.subscription_id.status = "suspended"
        with self.assertRaises(UserError):
            request.action_provision()
        self.assertEqual(request.state, "approved")
        self.assertFalse(request.tenant_id.provision_queued)

    def test_ready_only_after_a_real_verified_run(self):
        request = self._request()
        request.action_approve()
        request.action_provision()
        self.assertEqual(request.state, "provisioning")
        self.assertTrue(request.tenant_id.provision_queued)

        self._run_worker(ProvisionResult(
            True, "Provisioning succeeded.", "log", database_created=True,
            access_link="https://acme-trading-llc.example/web/signup?token=t"))
        self.assertEqual(request.state, "ready")
        self.assertEqual(request.tenant_id.state, "active")
        self.assertIn("acme-trading-llc.", request.workspace_url)
        self.assertTrue(request.tenant_id.access_link)

    def test_dry_run_does_not_make_the_request_ready(self):
        request = self._request()
        request.action_approve()
        request.action_provision()
        # The real queue worker on a server that may not create databases.
        with patch.dict(os.environ, {ENV_FLAG: "0"}), patch.object(self.env.cr, "commit"):
            self.env["mumtaz.tenant"]._cron_run_provision_queue()
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.tenant_id.state, "draft")
        self.assertFalse(request.tenant_id.provisioned_on)

    def test_failed_run_blocks_a_blind_retry(self):
        request = self._request()
        request.action_approve()
        request.action_provision()
        self._run_worker(ProvisionResult(
            False, "Provisioning failed: boom", "log", database_created=True))
        self.assertEqual(request.state, "failed")
        with self.assertRaises(UserError):
            request.action_provision()

    # ── who may do what ───────────────────────────────────────────────────

    def test_only_super_admin_approves_and_provisions(self):
        request = self._request()
        tenant_admin = new_test_user(
            self.env, login="cp_tenant_admin",
            groups="base.group_user,mumtaz_control_plane.group_mumtaz_tenant_admin")
        self.assertEqual(request.with_user(tenant_admin).name, "Acme Trading LLC")
        with self.assertRaises(AccessError):
            request.with_user(tenant_admin).action_approve()

        super_admin = new_test_user(
            self.env, login="cp_super_admin",
            groups="base.group_user,mumtaz_control_plane.group_mumtaz_super_admin")
        request.with_user(super_admin).action_approve()
        request.with_user(super_admin).action_provision()
        self.assertEqual(request.state, "provisioning")
        with self.assertRaises(AccessError):
            request.with_user(tenant_admin).action_provision()

    def test_ordinary_staff_cannot_see_requests(self):
        request = self._request()
        staff = new_test_user(self.env, login="cp_plain_staff", groups="base.group_user")
        with self.assertRaises(AccessError):
            request.with_user(staff).read(["name"])
        portal = new_test_user(self.env, login="cp_portal", groups="base.group_portal")
        with self.assertRaises(AccessError):
            request.with_user(portal).read(["name"])

    # ── public intake ─────────────────────────────────────────────────────

    def _public(self, **overrides):
        payload = dict({
            "organization": "Public Co", "contact_name": "Pat Public",
            "email": "pat@public.example", "product": "erp",
        }, **overrides)
        # sudo: mirrors the controller, which calls the method for a visitor with no rights
        return self.Request.sudo()._register_public(payload)

    def test_public_intake_is_closed_by_default(self):
        with self.assertRaises(UserError):
            self._public()
        self.assertFalse(self.Request.search([("email", "=", "pat@public.example")]))

    def test_public_intake_only_ever_creates_a_pending_request(self):
        self.env["ir.config_parameter"].set_param(PUBLIC_FLAG, "1")
        tenants_before = self.env["mumtaz.tenant"].search_count([])
        self.assertTrue(self._public())
        request = self.Request.search([("email", "=", "pat@public.example")])
        self.assertEqual(len(request), 1)
        self.assertEqual((request.state, request.source), ("new", "public"))
        self.assertFalse(request.tenant_id or request.subscription_id or request.partner_id)
        self.assertEqual(self.env["mumtaz.tenant"].search_count([]), tenants_before)

        # A repeat is answered the same way and adds nothing.
        self.assertTrue(self._public())
        self.assertEqual(self.Request.search_count([("email", "=", "pat@public.example")]), 1)
        # A filled honeypot is dropped silently.
        self.assertTrue(self._public(email="bot@spam.example", website="http://spam"))
        self.assertFalse(self.Request.search([("email", "=", "bot@spam.example")]))
        # A product that is not open is refused.
        with self.assertRaises(UserError):
            self._public(email="z@public.example", product="zaki")
        with self.assertRaises(UserError):
            self._public(email="not-an-email")

    def test_public_intake_has_an_hourly_cap(self):
        ICP = self.env["ir.config_parameter"]
        ICP.set_param(PUBLIC_FLAG, "1")
        ICP.set_param("mumtaz_control_plane.public_signup_hourly_cap", "2")
        self._public(email="a@public.example")
        self._public(email="b@public.example")
        with self.assertRaises(UserError):
            self._public(email="c@public.example")


@tagged("post_install", "-at_install")
class TestSignupRoute(HttpCase):
    def _post(self, **params):
        response = self.url_open(
            "/mumtaz/cp/signup",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json()

    def test_route_is_closed_until_switched_on(self):
        body = self._post(organization="Route Co", contact_name="Rae",
                          email="rae@route.example", product="erp")
        self.assertIn("error", body)
        self.assertFalse(self.env["mumtaz.signup.request"].search(
            [("email", "=", "rae@route.example")]))

    def test_route_records_a_pending_request_when_open(self):
        self.env["ir.config_parameter"].set_param(PUBLIC_FLAG, "1")
        body = self._post(organization="Route Co", contact_name="Rae",
                          email="rae@route.example", product="erp")
        self.assertEqual(body.get("result"), {"ok": True})
        request = self.env["mumtaz.signup.request"].search(
            [("email", "=", "rae@route.example")])
        self.assertEqual(request.state, "new")
        self.assertFalse(request.tenant_id)
        bad = self._post(organization="Route Co", contact_name="Rae",
                         email="nope", product="erp")
        self.assertFalse(bad["result"]["ok"])
