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

Two provisioners
----------------
``DryRunProvisioner`` checks the configuration and logs what would happen. It
creates nothing, and its result is marked ``simulated`` so that no caller can
mistake it for a provisioned tenant.

``RealProvisioner`` creates the database, installs the bundle, verifies the
outcome and issues a one-time set-password link for the tenant administrator.
It only runs when the server environment sets ``MUMTAZ_REAL_PROVISIONING=1``.

A tenant becomes ``active`` only after a real run that passed verification.
"""

import logging
import os
import secrets

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

class ProvisionResult:
    """Immutable result returned by ``BaseProvisioner.run``."""

    def __init__(self, success: bool, message: str = "", log: str = "",
                 simulated: bool = False, access_link: str = "",
                 database_created: bool = False):
        self.success = success
        self.message = message
        self.log = log
        # True when nothing was created (dry run). A simulated success must
        # never activate a tenant.
        self.simulated = simulated
        # One-time set-password link for the tenant administrator. It is a
        # credential: never write it to a log.
        self.access_link = access_link
        # True once the PostgreSQL database exists, including on a failed run.
        self.database_created = database_created

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        if self.simulated:
            status += " simulated"
        return f"<ProvisionResult [{status}] {self.message!r}>"


class ProvisioningDisabled(Exception):
    """Real provisioning was asked for on a server that has not enabled it."""


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

    #: True for provisioners that create nothing.
    simulated = False

    def __init__(self, odoo_env=None):
        """
        :param odoo_env: An Odoo ``api.Environment`` instance (the master DB
                         environment).  Required for real provisioners; optional
                         for dry-run.
        """
        self.env = odoo_env
        self._database_created = False

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

            log("Step 1/6: Creating database …")
            self._create_database(tenant)

            log("Step 2/6: Installing modules …")
            self._install_modules(tenant, modules)

            log("Step 3/6: Creating admin user …")
            self._create_admin_user(tenant)

            log("Step 4/6: Applying settings and branding …")
            self._apply_settings(tenant)

            log("Step 5/6: Verifying the result …")
            self._verify(tenant, modules)

            log("Step 6/6: Issuing the administrator's set-password link …")
            access_link = self._issue_access_link(tenant) or ""

            if self.simulated:
                log("Dry run passed. Nothing was created.")
                return ProvisionResult(
                    True, "Dry run passed. Nothing was created.",
                    "\n".join(log_lines), simulated=True)

            log("Provisioning complete.")
            return ProvisionResult(
                True, "Provisioning succeeded.", "\n".join(log_lines),
                access_link=access_link, database_created=True)

        except Exception as exc:  # pylint: disable=broad-except
            msg = f"Provisioning failed: {exc}"
            _logger.exception("[Provisioning] %s — %s", tenant.name, msg)
            log_lines.append(msg)
            if self._database_created:
                # Never dropped automatically: a person decides what happens
                # to a database, even a half-built one.
                log_lines.append(
                    "Database '%s' exists but is incomplete. An administrator "
                    "must inspect it and remove it before this tenant can be "
                    "provisioned again." % tenant.database_name)
            return ProvisionResult(
                False, msg, "\n".join(log_lines),
                simulated=self.simulated,
                database_created=self._database_created)

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

    def _verify(self, tenant, modules):
        """Raise unless the tenant database is in the state that was asked for."""

    def _issue_access_link(self, tenant):
        """Return a one-time set-password link for the tenant administrator."""
        return ""

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

    Every step logs what *would* happen. The result is marked ``simulated``;
    callers leave the tenant in draft.
    """

    simulated = True

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
        import odoo.sql_db

        db_name = tenant.database_name
        if not db_name:
            raise ValueError("Tenant has no database_name.")
        if db_service.exp_db_exist(db_name):
            raise ValueError("Database '%s' already exists." % db_name)
        login = tenant.admin_email or "admin"
        # With no password on the record the administrator gets a random one
        # that nobody ever sees; they set their own through the one-time link.
        password = tenant.admin_password or secrets.token_urlsafe(32)
        # The two calls below are what odoo.service.db.exp_create_database
        # does. That public wrapper refuses to run when the server hides its
        # database manager (list_db = False), which is how a multi-tenant
        # server should be configured. Creating databases is this service's
        # job, authorised by the provisioning permission and the server-side
        # switch, not by the database-manager screen.
        db_service._create_empty_database(db_name)
        self._database_created = True
        db_service._initialize_db(
            db_name, False, "en_US", password, login=login)
        # _initialize_db logs and swallows its own failures, so look.
        with odoo.sql_db.db_connect(db_name).cursor() as cr:
            cr.execute("SELECT to_regclass('ir_module_module'), to_regclass('res_users')")
            if not all(cr.fetchone()):
                raise RuntimeError(
                    "Database '%s' was created but Odoo did not initialise it. "
                    "See the server log." % db_name)
            cr.execute("SELECT state FROM ir_module_module WHERE name = 'base'")
            row = cr.fetchone()
            if not row or row[0] != "installed":
                raise RuntimeError(
                    "Database '%s' was created but the base module is not "
                    "installed. See the server log." % db_name)
        # Clear the password immediately after use so it is never left on the
        # control-plane record if the provisioner crashes in a later step.
        tenant.write({"admin_password": False})
        if self.env and hasattr(self.env, "cr"):
            self.env.cr.commit()

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
        import odoo
        from odoo import api, SUPERUSER_ID

        registry = odoo.modules.registry.Registry(tenant.database_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            company = env.ref("base.main_company", raise_if_not_found=False)
            if company and tenant.name:
                company.name = tenant.name
            # sudo: system parameter; only administrators may read ir.config_parameter
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

    def _verify(self, tenant, modules):
        import odoo
        from odoo import api, SUPERUSER_ID

        registry = odoo.modules.registry.Registry(tenant.database_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            installed = set(env["ir.module.module"].search(
                [("name", "in", modules), ("state", "=", "installed")]
            ).mapped("name"))
            missing = [m for m in modules if m not in installed]
            if missing:
                raise RuntimeError(
                    "Modules not installed: %s." % ", ".join(missing))
            admin = env.ref("base.user_admin", raise_if_not_found=False)
            if not admin or not admin.active:
                raise RuntimeError("The administrator user is missing.")
            if tenant.admin_email and admin.login != tenant.admin_email:
                raise RuntimeError(
                    "The administrator login was not set to the tenant's "
                    "admin email.")

    def _issue_access_link(self, tenant):
        import odoo
        from odoo import api, SUPERUSER_ID

        registry = odoo.modules.registry.Registry(tenant.database_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            admin = env.ref("base.user_admin", raise_if_not_found=False)
            if not admin or "signup_type" not in admin.partner_id._fields:
                # auth_signup is absent: no link can be issued, and the
                # random password is unknown. Say so instead of pretending.
                raise RuntimeError(
                    "Cannot issue a set-password link: the tenant database "
                    "has no auth_signup module.")
            partner = admin.partner_id
            # Odoo's own invitation token: signed with the tenant
            # database's secret, time-limited, and void after first login.
            partner.signup_prepare(signup_type="signup")
            return partner._get_signup_url_for_action()[partner.id]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Default to the safe dry-run provisioner.
PROVISIONER_CLASS = DryRunProvisioner


def real_provisioning_enabled() -> bool:
    """True when this server is allowed to create tenant databases."""
    return os.environ.get("MUMTAZ_REAL_PROVISIONING") == "1"


def get_provisioner(odoo_env=None, dry_run=None) -> BaseProvisioner:
    """Return the provisioner to use.

    :param dry_run: ``True`` always simulates. ``False`` asks for a real run
        and raises ``ProvisioningDisabled`` when the server has not enabled
        one. ``None`` (background queue) runs for real when the server allows
        it and simulates otherwise.

    Real database creation is opt-in per server: set
    ``MUMTAZ_REAL_PROVISIONING=1`` in the service environment.
    """
    if dry_run:
        return DryRunProvisioner(odoo_env=odoo_env)
    if real_provisioning_enabled():
        _logger.info("[Provisioning] Real provisioner active.")
        return RealProvisioner(odoo_env=odoo_env)
    if dry_run is False:
        raise ProvisioningDisabled(
            "Real provisioning is switched off on this server "
            "(MUMTAZ_REAL_PROVISIONING is not set).")
    return DryRunProvisioner(odoo_env=odoo_env)
