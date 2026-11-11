"""Shared fixtures for the Jawhar Odoo integration tests.

Synthetic users and data only (docs/mumtaz-jewel/CLAUDE.md). Nothing here
touches a real client, a real rate feed or an outbound channel.
"""
from odoo.tests import TransactionCase

GROUP_USER = 'mumtaz_jewellery.group_jewellery_user'
GROUP_MANAGER = 'mumtaz_jewellery.group_jewellery_manager'

# Deterministic figures reused across tests. The expected totals below are the
# pricing engine's own documented numbers (see tests/test_pricing.py), so a
# drift between the engine and the Odoo layer shows up as a failure here.
RATE_PER_GRAM = 100.0
VAT_RATE = '5'
GROSS_G = 12.0
STONE_G = 2.0          # net metal weight = 10 g
EXPECTED_TOTAL = 1130.50   # 10 g @ 22K, rate 100, wastage 2%, making 10%, stones 50, VAT 5%


class JewelCommon(TransactionCase):
    """Five synthetic user types, created once per class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.group_user = cls.env.ref(GROUP_USER)
        cls.group_manager = cls.env.ref(GROUP_MANAGER)
        cls.base_user = cls.env.ref('base.group_user')

        # A plain internal employee with no jewellery rights at all.
        cls.user_outsider = cls._make_user('demo_outsider', cls.base_user)
        # Counter staff: jewellery user, not a manager.
        cls.user_staff = cls._make_user('demo_staff', cls.base_user, cls.group_user)
        # Two distinct jewellery managers: the maker and the checker.
        cls.user_manager_a = cls._make_user('demo_manager_a', cls.base_user, cls.group_manager)
        cls.user_manager_b = cls._make_user('demo_manager_b', cls.base_user, cls.group_manager)

        cls._set_param('mumtaz_jewellery.allow_self_approval', '0')
        cls._set_param('mumtaz_jewellery.vat_rate', VAT_RATE)
        cls._set_param('mumtaz_jewellery.exchange_approval_threshold', '0')

    # -- helpers -------------------------------------------------------
    @classmethod
    def _make_user(cls, login, *groups):
        """Create a user, tolerating the res.users groups field rename.

        Odoo renamed ``res.users.groups_id`` to ``group_ids``; picking the
        field that actually exists keeps this suite runnable on 17, 18 and 19
        without editing.
        """
        model = cls.env['res.users']
        field = 'group_ids' if 'group_ids' in model._fields else 'groups_id'
        return model.with_context(
            no_reset_password=True, mail_create_nolog=True, tracking_disable=True,
        ).create({
            'name': 'DEMO %s' % login,
            'login': login,
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            field: [(6, 0, [g.id for g in groups])],
        })

    @classmethod
    def _set_param(cls, key, value):
        cls.env['ir.config_parameter'].sudo().set_param(key, value)

    def _draft_rate(self, user, rate=RATE_PER_GRAM):
        """A draft rate entered by ``user`` (so create_uid is that user)."""
        return self.env['jewellery.gold.rate'].with_user(user).create({
            'rate_per_gram': rate,
            'company_id': self.company.id,
        })

    def _approved_rate(self, rate=RATE_PER_GRAM):
        """A rate through the real maker-checker path: A enters, B approves."""
        record = self._draft_rate(self.user_manager_a, rate)
        record.with_user(self.user_manager_b).action_approve()
        return record

    def _jewellery_product(self):
        values = {
            'name': 'DEMO Bangle 22K',
            'is_jewellery': True,
            'tracking': 'serial',
            'jewellery_karat': '22',
            'jewellery_wastage_pct': 2.0,
            'jewellery_making_type': 'percent',
            'jewellery_making_value': 10.0,
        }
        model = self.env['product.template']
        # ``is_storable`` replaced ``type='product'`` for stockable goods.
        if 'is_storable' in model._fields:
            values['is_storable'] = True
        else:
            values['type'] = 'product'
        return model.create(values)

    def _piece(self, product=None):
        product = product or self._jewellery_product()
        return self.env['stock.lot'].create({
            'name': 'DEMO-PIECE-0001',
            'product_id': product.product_variant_id.id,
            'company_id': self.company.id,
            'gross_weight_g': GROSS_G,
            'stone_weight_g': STONE_G,
            'karat': '22',
            'wastage_pct': 2.0,
            'making_type': 'percent',
            'making_value': 10.0,
            'stones_value': 50.0,
        })
