import os
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

from ..services import provisioning
from ..services.provisioning import (
    DryRunProvisioner,
    ProvisioningDisabled,
    ProvisionResult,
    RealProvisioner,
    get_provisioner,
)

WIZARD = "odoo.addons.mumtaz_tenant_manager.wizards.provision_wizard"
ENV_FLAG = "MUMTAZ_REAL_PROVISIONING"

# Modules that belong to the control database only.
CONTROL_PLANE_ONLY = {
    "mumtaz_tenant_manager", "mumtaz_control_plane", "mumtaz_billing_stripe",
    "mumtaz_subdomain_routing",
}


class _StubProvisioner:
    """Stands in for RealProvisioner: no database is touched in unit tests.
    The real one is exercised end to end by scripts/tenant_journey_ci.sh."""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def run(self, tenant):
        self.calls += 1
        return self.result


@tagged("post_install", "-at_install")
class TestProvisioningOutcome(TransactionCase):
    """A tenant is `active` only after a real, verified provisioning run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bundle = cls.env.ref("mumtaz_tenant_manager.bundle_mumtaz_erp")
        cls.tenant = cls.env["mumtaz.tenant"].create({
            "name": "Unit Test Org",
            "code": "unit-test-org",
            "database_name": "stg_unit_test_org",
            "subdomain": "unit-test-org",
            "environment": "staging",
            "bundle_id": cls.bundle.id,
            "admin_email": "owner@unit-test.example",
            "admin_name": "Unit Owner",
        })

    def _wizard(self, **vals):
        return self.env["mumtaz.provision.wizard"].create(
            dict({"tenant_id": self.tenant.id}, **vals))

    # ── choosing the provisioner ──────────────────────────────────────────

    def test_provisioner_choice(self):
        with patch.dict(os.environ, {ENV_FLAG: "0"}):
            self.assertIsInstance(get_provisioner(dry_run=True), DryRunProvisioner)
            self.assertIsInstance(get_provisioner(), DryRunProvisioner)
            with self.assertRaises(ProvisioningDisabled):
                get_provisioner(dry_run=False)
        with patch.dict(os.environ, {ENV_FLAG: "1"}):
            # The checkbox wins even on a server that allows real runs.
            self.assertIsInstance(get_provisioner(dry_run=True), DryRunProvisioner)
            self.assertIsInstance(get_provisioner(dry_run=False), RealProvisioner)
            self.assertIsInstance(get_provisioner(), RealProvisioner)

    # ── dry run ───────────────────────────────────────────────────────────

    def test_dry_run_never_activates(self):
        # Even with real provisioning enabled on the server, a ticked
        # "Dry Run" box must create nothing and leave the tenant in draft.
        with patch.dict(os.environ, {ENV_FLAG: "1"}):
            wizard = self._wizard(dry_run=True)
            wizard.action_run_provisioning()
        self.assertTrue(wizard.result_success)
        self.assertEqual(self.tenant.state, "draft")
        self.assertFalse(self.tenant.provisioned_on)
        self.assertIn("Nothing was created", self.tenant.provision_log)
        import odoo.service.db as db_service
        self.assertFalse(db_service.exp_db_exist(self.tenant.database_name))

    def test_real_run_refused_when_server_disallows_it(self):
        with patch.dict(os.environ, {ENV_FLAG: "0"}):
            wizard = self._wizard(dry_run=False)
            with self.assertRaises(UserError):
                wizard.action_run_provisioning()
        self.assertEqual(self.tenant.state, "draft")
        self.assertFalse(self.tenant.provision_log)

    def test_queue_without_real_provisioning_does_not_activate(self):
        self.tenant.action_queue_provisioning()
        self.assertEqual(self.tenant.state, "provisioning")
        with patch.dict(os.environ, {ENV_FLAG: "0"}), \
                patch.object(self.env.cr, "commit"):
            self.env["mumtaz.tenant"]._cron_run_provision_queue()
        self.assertEqual(self.tenant.state, "draft")
        self.assertFalse(self.tenant.provision_queued)
        self.assertFalse(self.tenant.provisioned_on)

    # ── real run (stubbed) ────────────────────────────────────────────────

    def test_verified_real_run_activates_and_stores_the_link(self):
        self.tenant.admin_password = "temporary"
        stub = _StubProvisioner(ProvisionResult(
            True, "Provisioning succeeded.", "log",
            access_link="https://unit-test-org.example/web/signup?token=abc",
            database_created=True))
        with patch(WIZARD + ".get_provisioner", return_value=stub):
            self._wizard(dry_run=False).action_run_provisioning()
        self.assertEqual(stub.calls, 1)
        self.assertEqual(self.tenant.state, "active")
        self.assertTrue(self.tenant.provisioned_on)
        self.assertFalse(self.tenant.admin_password)
        self.assertIn("token=abc", self.tenant.access_link)
        self.assertTrue(self.tenant.access_link_issued_on)

    def test_failure_leaves_draft_and_flags_the_leftover_database(self):
        stub = _StubProvisioner(ProvisionResult(
            False, "Provisioning failed: boom", "log", database_created=True))
        with patch(WIZARD + ".get_provisioner", return_value=stub):
            wizard = self._wizard(dry_run=False)
            wizard.action_run_provisioning()
        self.assertFalse(wizard.result_success)
        self.assertEqual(self.tenant.state, "draft")
        self.assertTrue(self.tenant.database_needs_cleanup)
        self.assertFalse(self.tenant.access_link)
        # A later failure that created nothing must not clear the flag.
        self.tenant._apply_provision_result(
            ProvisionResult(False, "Database already exists.", "log"))
        self.assertTrue(self.tenant.database_needs_cleanup)

    @mute_logger("odoo.addons.mumtaz_tenant_manager.services.provisioning")
    def test_base_run_reports_a_hook_failure(self):
        class Broken(provisioning.DryRunProvisioner):
            def _install_modules(self, tenant, modules):
                raise RuntimeError("install blew up")

        result = Broken(self.env).run(self.tenant)
        self.assertFalse(result.success)
        self.assertIn("install blew up", result.message)

    # ── who may provision ─────────────────────────────────────────────────

    def test_platform_manager_cannot_provision(self):
        manager = new_test_user(
            self.env, login="tm_manager",
            groups="base.group_user,mumtaz_tenant_manager.group_mumtaz_platform_manager")
        tenant = self.tenant.with_user(manager)
        # The manager group may edit the record...
        tenant.write({"notes": "edited by a manager"})
        # ...but not start provisioning, not even over RPC.
        with self.assertRaises(AccessError):
            tenant.action_queue_provisioning()
        self.assertEqual(self.tenant.state, "draft")

    def test_platform_admin_can_queue(self):
        admin = new_test_user(
            self.env, login="tm_admin",
            groups="base.group_user,mumtaz_tenant_manager.group_mumtaz_platform_admin")
        self.tenant.with_user(admin).action_queue_provisioning()
        self.assertTrue(self.tenant.provision_queued)

    def test_access_link_is_hidden_from_managers(self):
        self.tenant.access_link = "https://x.example/web/signup?token=secret"
        manager = new_test_user(
            self.env, login="tm_manager2",
            groups="base.group_user,mumtaz_tenant_manager.group_mumtaz_platform_manager")
        with self.assertRaises(AccessError):
            self.tenant.with_user(manager).read(["access_link"])

    # ── staging naming ────────────────────────────────────────────────────

    def test_staging_database_name_must_carry_the_prefix(self):
        with self.assertRaises(ValidationError):
            self.tenant.database_name = "unit_test_org"
        with self.assertRaises(ValidationError):
            self.env["mumtaz.tenant"].create({
                "name": "Prod Org", "code": "prod-org",
                "database_name": "stg_prod_org", "environment": "production",
            })

    # ── the ERP install profile ───────────────────────────────────────────

    def test_erp_profile_modules_exist_and_stay_out_of_the_control_plane(self):
        names = self.bundle.get_base_module_list()
        Module = self.env["ir.module.module"]
        known = Module.search([("name", "in", names)])
        self.assertEqual(
            sorted(known.mapped("name")), sorted(names),
            "Every module of the ERP profile must exist on this server; a "
            "missing one would be skipped silently at provisioning.")
        closure, todo = set(), set(names)
        while todo:
            name = todo.pop()
            if name in closure:
                continue
            closure.add(name)
            module = Module.search([("name", "=", name)], limit=1)
            todo.update(module.dependencies_id.mapped("name"))
        self.assertFalse(
            closure & CONTROL_PLANE_ONLY,
            "The ERP profile must not pull control-plane modules into a "
            "customer database.")
