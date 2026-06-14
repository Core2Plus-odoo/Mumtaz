"""
Mumtaz Tenant Provisioning Service
===================================
Abstraction layer that orchestrates the creation and initialisation of a new
isolated tenant Odoo database.

Architecture note
-----------------
Each tenant runs in its OWN PostgreSQL database.  This service is responsible
for:

  1. Creating the PostgreSQL database via Odoo's db-manager API.
  2. Installing the required module bundle (+ extras) into the new DB.
  3. Creating the initial admin user.
  4. Applying baseline settings (company name, branding, etc.).
  5. Marking the tenant record as ``active``.

Current implementation
-----------------------
The service provides a clean interface and a ``DryRunProvisioner`` that
simulates the flow without making actual database calls.  This keeps the
control-plane module installable on any Odoo instance while the operator
decides on the deployment topology.

To wire up real provisioning, subclass ``BaseProvisioner`` and override the
``_create_database``, ``_install_modules``, ``_create_admin_user`` and
``_apply_settings`` hooks.  Then register your subclass via the
``PROVISIONER_CLASS`` module-level variable or use the ``get_provisioner``
factory.
"""

import logging

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

class ProvisionResult:
    """Immutable result returned by ``BaseProvisioner.run``."""

    def __init__(self, success: bool, message: str = "", log: str = ""):
        self.success = success
        self.message = message
        self.log = log

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return f"<ProvisionResult [{status}] {self.message!r}>"


# ---------------------------------------------------------------------------
# Base provisioner
# ---------------------------------------------------------------------------

class BaseProvisioner:
    """
    Override this class to implement real provisioning.

    Methods to override:
      - ``_create_database(tenant)``
      - ``_install_modules(tenant, modules)``
      - ``_create_admin_user(tenant)``
      - ``_apply_settings(tenant)``

    Each hook must raise an exception on failure; the base ``run`` method
    catches and logs all exceptions.
    """

    def __init__(self, odoo_env=None):
        """
        :param odoo_env: An Odoo ``api.Environment`` instance (the master DB
                         environment).  Required for real provisioners; optional
                         for dry-run.
        """
        self.env = odoo_env

    # -- Public API --------------------------------------------------------

    def run(self, tenant):
        """
        Execute the full provisioning sequence for ``tenant`` (a
        ``mumtaz.tenant`` recordset with exactly one record).

        Returns a ``ProvisionResult``.
        """
        tenant.ensure_one()
        log_lines = []

        def log(msg):
            _logger.info("[Provisioning] %s — %s", tenant.name, msg)
            log_lines.append(msg)

        try:
            log("Starting provisioning sequence.")

            # Resolve the full module list for this tenant.
            modules = self._resolve_modules(tenant)
            log(f"Modules to install: {', '.join(modules) or '(none)'}")

            log("Step 1/4: Creating database …")
            self._create_database(tenant)

            log("Step 2/4: Installing modules …")
            self._install_modules(tenant, modules)

            log("Step 3/4: Creating admin user …")
            self._create_admin_user(tenant)

            log("Step 4/4: Applying settings and branding …")
            self._apply_settings(tenant)

            log("Provisioning complete.")
            return ProvisionResult(True, "Provisioning succeeded.", "\n".join(log_lines))

        except Exception as exc:  # pylint: disable=broad-except
            msg = f"Provisioning failed: {exc}"
            _logger.exception("[Provisioning] %s — %s", tenant.name, msg)
            log_lines.append(msg)
            return ProvisionResult(False, msg, "\n".join(log_lines))

    # -- Hooks (override in subclasses) ------------------------------------

    def _create_database(self, tenant):
        raise NotImplementedError(
            "_create_database must be implemented by a concrete provisioner."
        )

    def _install_modules(self, tenant, modules):
        raise NotImplementedError(
            "_install_modules must be implemented by a concrete provisioner."
        )

    def _create_admin_user(self, tenant):
        raise NotImplementedError(
            "_create_admin_user must be implemented by a concrete provisioner."
        )

    def _apply_settings(self, tenant):
        raise NotImplementedError(
            "_apply_settings must be implemented by a concrete provisioner."
        )

    # -- Shared helpers ----------------------------------------------------

    def _resolve_modules(self, tenant):
        """Return the de-duplicated list of modules to install."""
        modules = []
        if tenant.bundle_id:
            modules.extend(tenant.bundle_id.get_base_module_list())
        modules.extend(tenant.get_extra_module_list())
        # Deduplicate while preserving order.
        seen = set()
        result = []
        for m in modules:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result


# ---------------------------------------------------------------------------
# Dry-run provisioner (default / safe)
# ---------------------------------------------------------------------------

class DryRunProvisioner(BaseProvisioner):
    """
    Simulates the provisioning workflow without making any real system calls.

    Safe to use during development and when the Odoo DB-manager endpoint has
    not yet been configured.  Every step logs what *would* happen and
    returns success.
    """

    def _create_database(self, tenant):
        _logger.info(
            "[DryRun] Would create PostgreSQL database '%s'.", tenant.database_name
        )

    def _install_modules(self, tenant, modules):
        _logger.info(
            "[DryRun] Would install modules in '%s': %s",
            tenant.database_name,
            ", ".join(modules) or "(none)",
        )

    def _create_admin_user(self, tenant):
        _logger.info(
            "[DryRun] Would create admin user '%s' (%s) in '%s'.",
            tenant.admin_name or "Administrator",
            tenant.admin_email or "(no email)",
            tenant.database_name,
        )

    def _apply_settings(self, tenant):
        _logger.info(
            "[DryRun] Would apply branding '%s' and baseline settings to '%s'.",
            tenant.brand_id.name if tenant.brand_id else "(no brand)",
            tenant.database_name,
        )


# ---------------------------------------------------------------------------
# Real provisioner (gated — creates actual PostgreSQL databases)
# ---------------------------------------------------------------------------

class RealProvisioner(BaseProvisioner):
    """
    Creates a real, isolated tenant database via Odoo's db service, installs
    the module bundle, configures the admin user and applies baseline settings.

    Enabled only when the environment variable ``MUMTAZ_REAL_PROVISIONING=1``
    is set (see ``get_provisioner``). Otherwise the safe ``DryRunProvisioner``
    is used so the control plane never creates databases by accident.
    """

    def _create_database(self, tenant):
        import odoo.service.db as db_service

        db_name = tenant.database_name
        if not db_name:
            raise ValueError("Tenant has no database_name.")
        if db_service.exp_db_exist(db_name):
            raise ValueError("Database '%s' already exists." % db_name)
        if not tenant.admin_password:
            raise ValueError(
                "An admin password is required to provision a real database."
            )
        login = tenant.admin_email or "admin"
        # Creates the DB, installs base and creates the admin user in one step.
        db_service.exp_create_database(
            db_name, False, "en_US",
            user_password=tenant.admin_password, login=login,
        )

    def _install_modules(self, tenant, modules):
        if not modules:
            return
        import odoo
        from odoo import api, SUPERUSER_ID

        registry = odoo.modules.registry.Registry(tenant.database_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            Module = env["ir.module.module"]
            found = Module.search([("name", "in", modules)])
            if set(modules) - set(found.mapped("name")):
                Module.update_list()
                found = Module.search([("name", "in", modules)])
            to_install = found.filtered(
                lambda m: m.state in ("uninstalled", "to install"))
            if to_install:
                to_install.button_immediate_install()

    def _create_admin_user(self, tenant):
        import odoo
        from odoo import api, SUPERUSER_ID

        registry = odoo.modules.registry.Registry(tenant.database_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            admin = env.ref("base.user_admin", raise_if_not_found=False)
            if not admin:
                return
            vals = {}
            if tenant.admin_name:
                vals["name"] = tenant.admin_name
            if tenant.admin_email:
                vals["login"] = tenant.admin_email
                vals["email"] = tenant.admin_email
            if vals:
                admin.write(vals)

    def _apply_settings(self, tenant):
        import os
        import odoo
        from odoo import api, SUPERUSER_ID

        registry = odoo.modules.registry.Registry(tenant.database_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            company = env.ref("base.main_company", raise_if_not_found=False)
            if company and tenant.name:
                company.name = tenant.name
            icp = env["ir.config_parameter"].sudo()
            # Plant the SSO shared secret so the control-panel bridge works.
            sso_secret = os.environ.get("ODOO_SSO_SECRET")
            if sso_secret:
                icp.set_param("mumtaz.sso_secret", sso_secret)
            # Point web.base.url at the tenant's public address.
            if tenant.subdomain:
                base = (icp.get_param("mumtaz.erp_base_domain")
                        or "erp.mumtaz.digital")
                icp.set_param("web.base.url",
                              "https://%s.%s" % (tenant.subdomain, base))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Default to the safe dry-run provisioner.
PROVISIONER_CLASS = DryRunProvisioner


def get_provisioner(odoo_env=None) -> BaseProvisioner:
    """Return the active provisioner instance.

    Real database creation is opt-in: set ``MUMTAZ_REAL_PROVISIONING=1`` in the
    environment to switch from the dry-run simulation to actual provisioning.
    """
    import os

    if os.environ.get("MUMTAZ_REAL_PROVISIONING") == "1":
        _logger.info("[Provisioning] Real provisioner active.")
        return RealProvisioner(odoo_env=odoo_env)
    return DryRunProvisioner(odoo_env=odoo_env)
