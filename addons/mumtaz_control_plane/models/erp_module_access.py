from odoo import api, models

# Map a Mumtaz ERP module key → candidate Odoo "user" group xmlids.
# Several candidates are listed for cross-version/edition resilience; any that
# don't resolve are simply skipped, so a wrong id is a harmless no-op and can
# never break access. System admins are always left untouched.
_MODULE_GROUPS = {
    "accounting":    ["account.group_account_invoice", "account.group_account_user"],
    "inventory":     ["stock.group_stock_user"],
    "sales":         ["sales_team.group_sale_salesman"],
    "hr":            ["hr.group_hr_user"],
    "manufacturing": ["mrp.group_mrp_user"],
}


class MumtazErpModuleAccess(models.AbstractModel):
    """Enforces ERP sub-module toggles by granting/revoking the module's Odoo
    *user* group for regular internal users. Best-effort and fully reversible;
    it touches only the named module's user group and never system admins, so
    it cannot lock anyone out of the platform.
    """
    _name = "mumtaz.erp.module.access"
    _description = "Mumtaz ERP Module Access Sync"

    @api.model
    def set_module_access(self, module_key, enabled):
        xmlids = _MODULE_GROUPS.get(module_key) or []
        if not xmlids:
            return False
        users = self.env["res.users"].sudo().search(
            [("share", "=", False), ("active", "=", True)]
        )
        # Odoo 19 renamed res.users.groups_id -> group_ids; stay version-robust.
        gfield = "group_ids" if "group_ids" in users._fields else "groups_id"
        sysgrp = self.env.ref("base.group_system", raise_if_not_found=False)
        if sysgrp:
            users = users.filtered(lambda u: sysgrp not in u[gfield])
        if not users:
            return True
        done = False
        for xmlid in xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                # Odoo 19 renamed res.groups.users -> user_ids; use set ops.
                ufield = "user_ids" if "user_ids" in group._fields else "users"
                if enabled:
                    group.sudo()[ufield] |= users
                else:
                    group.sudo()[ufield] -= users
                done = True
        return done
