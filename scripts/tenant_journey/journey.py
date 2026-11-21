"""Drive the registration journey inside the control database.

Fed to `odoo-bin shell` on stdin by scripts/tenant_journey_ci.sh, so `env` is
the control database's environment. It uses the same model methods the
operator's buttons and the scheduled worker call; nothing is stubbed.

Writes a JSON summary to $JOURNEY_OUT. Exits non-zero on the first surprise.
"""
import json
import os
import sys

MODE = os.environ["JOURNEY_MODE"]          # "real" or "dry"
ORG = os.environ["JOURNEY_ORG"]
EMAIL = os.environ["JOURNEY_EMAIL"]
OUT = os.environ["JOURNEY_OUT"]


def check(condition, message):
    if not condition:
        print("JOURNEY FAILED: %s" % message)
        env.cr.rollback()  # noqa: F821
        sys.exit(1)
    print("  ok  %s" % message)


Request = env["mumtaz.signup.request"]  # noqa: F821
Tenant = env["mumtaz.tenant"]  # noqa: F821
access = env["mumtaz.feature.access.service"]  # noqa: F821

# 1. Register organization — through the public intake, as the website would.
env["ir.config_parameter"].set_param("mumtaz_control_plane.public_signup", "1")  # noqa: F821
Request._register_public({
    "organization": ORG, "contact_name": "Journey Owner",
    "email": EMAIL, "product": "erp",          # 2. Choose Mumtaz ERP
})
request = Request.search([("email", "=", EMAIL)])
check(len(request) == 1 and request.state == "new", "registration recorded as a pending request")
check(not request.tenant_id, "no tenant exists before a person approves")
check(request.product_id.code == "erp", "product chosen: Mumtaz ERP")

# 3. Assign entitlement — approval creates the organization, the staging
#    tenant record and the trial subscription.
request.action_approve()
tenant = request.tenant_id
check(request.state == "approved" and tenant.state == "draft", "approved; tenant still draft")
check(tenant.environment == "staging" and tenant.database_name.startswith("stg_"),
      "tenant is staging: %s" % tenant.database_name)
grant = access.resolve_feature_access_by_code(tenant, "erp_access")
check(grant["effective_enabled"], "entitlement erp_access granted by the trial subscription")
check(not access.resolve_feature_access_by_code(tenant, "zaki_access")["effective_enabled"],
      "entitlement zaki_access not granted")
env.cr.commit()  # noqa: F821

# 4. Provision isolated staging tenant — queue, then the scheduled worker's method.
import odoo.service.db as db_service  # noqa: E402

check(not db_service.exp_db_exist(tenant.database_name), "database does not exist yet")
request.action_provision()
env.cr.commit()  # noqa: F821
Tenant._cron_run_provision_queue()
request.invalidate_recordset()
tenant.invalidate_recordset()

summary = {
    "mode": MODE,
    "request_state": request.state,
    "tenant_state": tenant.state,
    "database": tenant.database_name,
    "login": tenant.admin_email,
    "workspace_url": tenant.workspace_url,
    "modules": tenant.bundle_id.get_base_module_list(),
    "database_exists": bool(db_service.exp_db_exist(tenant.database_name)),
}

if MODE == "real":
    check(request.state == "ready", "request is ready (got %s)" % request.state)
    check(tenant.state == "active" and tenant.provisioned_on, "tenant is active")
    check(summary["database_exists"], "tenant database exists")
    check(bool(tenant.access_link), "administrator set-password link issued")
    check(not tenant.admin_password, "no password left on the control-plane record")
    summary["access_link"] = tenant.access_link
else:
    check(request.state == "approved", "dry run: request is back to approved, not ready")
    check(tenant.state == "draft" and not tenant.provisioned_on, "dry run: tenant is not active")
    check(not summary["database_exists"], "dry run: no database was created")
    check("Nothing was created" in (tenant.provision_log or ""), "dry run: log says nothing was created")

with open(OUT, "w") as handle:
    json.dump(summary, handle)
env.cr.commit()  # noqa: F821
print("JOURNEY OK (%s)" % MODE)
