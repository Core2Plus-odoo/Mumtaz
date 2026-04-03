import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Portal detection priority: first match wins.
# Each entry: (portal_type, list_of_group_xmlids_any_of_which_qualifies)
PORTAL_PRIORITY = [
    ('admin', [
        'mumtaz_tenant_manager.group_mumtaz_platform_admin',
        'mumtaz_tenant_manager.group_mumtaz_platform_manager',
    ]),
    ('zaki', [
        'mumtaz_cfo_base.group_mumtaz_cfo_manager',
        'mumtaz_cfo_base.group_mumtaz_cfo_user',
    ]),
    ('erp', [
        'mumtaz_core.group_mumtaz_super_admin',
        'mumtaz_core.group_mumtaz_manager',
        'mumtaz_core.group_mumtaz_sme_admin',
        'mumtaz_core.group_mumtaz_finance_user',
        'mumtaz_core.group_mumtaz_analyst',
        'mumtaz_core.group_mumtaz_partner_manager',
    ]),
    ('marketplace', [
        'mumtaz_marketplace.group_mumtaz_marketplace_manager',
        'mumtaz_marketplace.group_mumtaz_marketplace_user',
    ]),
]

PORTAL_URLS = {
    'admin':       '/mumtaz/portal/admin',
    'erp':         '/mumtaz/portal/erp',
    'zaki':        '/mumtaz/portal/zaki',
    'marketplace': '/mumtaz/portal/marketplace',
}

PORTAL_LABELS = {
    'admin':       'Admin Control Plane',
    'erp':         'ERP Portal',
    'zaki':        'ZAKI AI Portal',
    'marketplace': 'Marketplace',
}


class ResUsersPortal(models.Model):
    _inherit = 'res.users'

    mumtaz_portal_type = fields.Selection(
        selection=[
            ('admin',       'Admin Control Plane'),
            ('erp',         'ERP Portal'),
            ('zaki',        'ZAKI AI Portal'),
            ('marketplace', 'Marketplace Portal'),
            ('none',        'No Mumtaz Portal'),
        ],
        string='Mumtaz Portal',
        compute='_compute_mumtaz_portal_type',
        store=False,
        help=(
            'Computed portal assignment based on group membership. '
            'Priority order: Admin > ZAKI AI > ERP > Marketplace.'
        ),
    )

    @api.depends('groups_id')
    def _compute_mumtaz_portal_type(self):
        for user in self:
            user.mumtaz_portal_type = self._detect_portal_type(user)

    @api.model
    def _detect_portal_type(self, user):
        """Return the highest-priority portal type for a user.

        Iterates PORTAL_PRIORITY in order; returns the first portal
        for which the user belongs to any of the qualifying groups.
        Falls back to 'none' if no match found.
        """
        for portal_type, group_xmlids in PORTAL_PRIORITY:
            for xmlid in group_xmlids:
                try:
                    if user.has_group(xmlid):
                        return portal_type
                except Exception:
                    _logger.debug(
                        'Portal routing: group %s not found, skipping.', xmlid
                    )
        return 'none'

    def get_mumtaz_portal_redirect_url(self):
        """Return the correct portal landing URL for this user.

        Returns the Mumtaz portal URL when applicable, or '/web' for
        unmatched users so the standard Odoo backend is used.
        """
        self.ensure_one()
        portal_type = self._detect_portal_type(self)
        return PORTAL_URLS.get(portal_type, '/web')

    def get_mumtaz_portal_label(self):
        """Human-readable portal name for the switcher widget."""
        self.ensure_one()
        portal_type = self._detect_portal_type(self)
        return PORTAL_LABELS.get(portal_type, 'Mumtaz')

    def get_accessible_portals(self):
        """Return all portals this user can access (for the switcher).

        Super admins (group_mumtaz_super_admin) can see all portals.
        Other users see only their assigned portal.
        """
        self.ensure_one()
        is_super = self.has_group('mumtaz_core.group_mumtaz_super_admin')
        primary = self._detect_portal_type(self)

        if is_super:
            return [
                {'type': ptype, 'label': label, 'url': PORTAL_URLS[ptype]}
                for ptype, label in PORTAL_LABELS.items()
            ]

        if primary != 'none':
            return [{
                'type': primary,
                'label': PORTAL_LABELS[primary],
                'url': PORTAL_URLS[primary],
            }]

        return []
