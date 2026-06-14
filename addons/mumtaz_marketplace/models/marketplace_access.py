from odoo import api, models


class MumtazMarketplaceAccess(models.AbstractModel):
    """Enforces the Marketplace app toggle by granting/revoking the
    *Marketplace User* group on every internal user.

    Scoped strictly to this addon's own group — it never touches core Odoo
    groups, so disabling the marketplace cannot lock users out of the rest of
    the ERP. Re-enabling restores access (fully reversible).
    """
    _name = "mumtaz.marketplace.access"
    _description = "Mumtaz Marketplace Access Sync"

    @api.model
    def set_access(self, enabled):
        group = self.env.ref(
            "mumtaz_marketplace.group_mumtaz_marketplace_user",
            raise_if_not_found=False,
        )
        if not group:
            return False
        users = self.env["res.users"].sudo().search(
            [("share", "=", False), ("active", "=", True)]
        )
        if not users:
            return True
        # Odoo 19 renamed res.groups.users -> user_ids; stay version-robust.
        ufield = "user_ids" if "user_ids" in group._fields else "users"
        if enabled:
            group.sudo()[ufield] |= users
        else:
            group.sudo()[ufield] -= users
        return True

    @api.model
    def _sync_from_feature(self):
        """Apply the current marketplace_access feature state to the group.
        Enabled by default unless an explicit force_off tenant override exists.
        Called on install/upgrade so the group always matches the toggle."""
        enabled = True
        if "mumtaz.feature" in self.env and "mumtaz.tenant.feature" in self.env:
            feat = self.env["mumtaz.feature"].sudo().search(
                [("code", "=", "marketplace_access")], limit=1
            )
            if feat:
                override = self.env["mumtaz.tenant.feature"].sudo().search(
                    [("feature_id", "=", feat.id)], limit=1
                )
                if override and override.override_mode == "force_off":
                    enabled = False
        return self.set_access(enabled)
