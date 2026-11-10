"""Build the DEMO dataset.

Synthetic data only. Everything is prefixed "DEMO" so it is obvious in the
UI that nothing here is real. Idempotent: a marker parameter stops a second
install from duplicating the records.
"""
import logging
from datetime import timedelta

from odoo import fields

_logger = logging.getLogger(__name__)

MARKER = 'mumtaz_jewellery_demo.seeded'

# 24K per gram, in the company currency. A round, obviously-synthetic figure.
DEMO_RATE_PER_GRAM = 100.0

PRODUCTS = [
    # name, karat, wastage %, making type, making value
    ('DEMO Bangle 22K', '22', 2.0, 'percent', 10.0),
    ('DEMO Chain 21K', '21', 1.5, 'per_gram', 12.5),
    ('DEMO Ring 18K with stones', '18', 1.0, 'fixed', 250.0),
]

PIECES = [
    # product index, serial, gross g, stone g, stones value, rfid, certificate
    (0, 'DEMO-BNG-0001', 24.500, 0.0, 0.0, 'DEMO-RFID-0001', ''),
    (0, 'DEMO-BNG-0002', 31.200, 0.0, 0.0, 'DEMO-RFID-0002', ''),
    (1, 'DEMO-CHN-0001', 18.750, 0.0, 0.0, 'DEMO-RFID-0003', ''),
    (1, 'DEMO-CHN-0002', 42.100, 0.0, 0.0, 'DEMO-RFID-0004', ''),
    (2, 'DEMO-RNG-0001', 6.400, 1.1, 1800.0, 'DEMO-RFID-0005', 'DEMO-CERT-55121'),
    (2, 'DEMO-RNG-0002', 7.900, 1.6, 2600.0, 'DEMO-RFID-0006', 'DEMO-CERT-55122'),
]

CLIENTS = [
    # name, tier, preferred karats, typical budget, occasion kind, days ahead
    ('DEMO Client Alpha', 'standard', '22', 4000.0, 'birthday', 30),
    ('DEMO Client Bravo', 'preferred', '22,21', 12000.0, 'anniversary', 14),
    ('DEMO Client Charlie', 'private', '21', 45000.0, 'wedding', 21),
    ('DEMO Client Delta', 'royal', '22', 150000.0, 'eid', 40),
]


def _user_groups_field(env):
    """``res.users.groups_id`` was renamed to ``group_ids``."""
    return 'group_ids' if 'group_ids' in env['res.users']._fields else 'groups_id'


def _make_demo_manager(env, login, name):
    existing = env['res.users'].with_context(active_test=False).search(
        [('login', '=', login)], limit=1)
    if existing:
        return existing
    field = _user_groups_field(env)
    return env['res.users'].with_context(
        no_reset_password=True, mail_create_nolog=True, tracking_disable=True,
    ).create({
        'name': name,
        'login': login,
        'company_id': env.company.id,
        'company_ids': [(6, 0, [env.company.id])],
        field: [(6, 0, [
            env.ref('base.group_user').id,
            env.ref('mumtaz_jewellery.group_jewellery_manager').id,
            env.ref('mumtaz_jewellery_vip.group_vip_manager').id,
        ])],
    })


def _seed_rate(env):
    """Enter a rate as one manager and approve it as another: the real path."""
    maker = _make_demo_manager(env, 'demo_rate_maker', 'DEMO Rate Maker')
    checker = _make_demo_manager(env, 'demo_rate_checker', 'DEMO Rate Checker')
    rate = env['jewellery.gold.rate'].with_user(maker).create({
        'rate_per_gram': DEMO_RATE_PER_GRAM,
        'company_id': env.company.id,
        'source': 'manual',
    })
    rate.with_user(checker).action_approve()
    if rate.state != 'approved':
        raise AssertionError('DEMO seed: the gold rate was not approved')
    return rate, maker, checker


def _seed_products(env):
    template = env['product.template']
    storable = 'is_storable' in template._fields
    products = []
    for name, karat, wastage, making_type, making_value in PRODUCTS:
        values = {
            'name': name,
            'is_jewellery': True,
            'tracking': 'serial',
            'jewellery_karat': karat,
            'jewellery_wastage_pct': wastage,
            'jewellery_making_type': making_type,
            'jewellery_making_value': making_value,
        }
        if storable:
            values['is_storable'] = True
        else:
            values['type'] = 'product'
        products.append(template.create(values))
    return products


def _seed_pieces(env, products):
    lots = env['stock.lot']
    created = lots
    for index, serial, gross, stone, stones_value, rfid, certificate in PIECES:
        product = products[index]
        created |= lots.create({
            'name': serial,
            'product_id': product.product_variant_id.id,
            'company_id': env.company.id,
            'gross_weight_g': gross,
            'stone_weight_g': stone,
            'stones_value': stones_value,
            'rfid_tag': rfid,
            'certificate_ref': certificate,
        })
    return created


def _put_pieces_in_stock(env, lots):
    """One of each piece on hand, so stock-value and offer views have data."""
    warehouse = env['stock.warehouse'].search(
        [('company_id', '=', env.company.id)], limit=1)
    if not warehouse:
        _logger.warning('DEMO seed: no warehouse found; pieces left off-hand')
        return 0
    location = warehouse.lot_stock_id
    count = 0
    for lot in lots:
        env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': lot.product_id.id,
            'lot_id': lot.id,
            'location_id': location.id,
            'inventory_quantity': 1.0,
        }).action_apply_inventory()
        count += 1
    return count


def _seed_clients(env, manager, lots):
    partners = env['res.partner']
    today = fields.Date.context_today(env['res.partner'])
    created = partners
    for name, tier, karats, budget, occasion_kind, days in CLIENTS:
        values = {
            'name': name,
            'jewellery_tier': tier,
            'preferred_karats': karats,
            'typical_budget': budget,
            'taste_notes': 'DEMO record. Synthetic preferences for the demo only.',
            'comment': 'DEMO data: not a real client.',
        }
        # Private and Royal clients must have a named relationship manager.
        if tier in ('private', 'royal'):
            values['relationship_manager_id'] = manager.id
        partner = partners.create(values)
        env['jewellery.occasion'].create({
            'partner_id': partner.id,
            'kind': occasion_kind,
            'date': today + timedelta(days=days),
            'recurring': True,
            'lead_days': 21,
            'note': 'DEMO occasion.',
        })
        created |= partner

    # One piece out on approval, due back shortly, so the owner screen and the
    # memo reminder have something to show.
    if created and lots:
        env['jewellery.approval.memo'].create({
            'partner_id': created[1].id,
            'lot_ids': [(6, 0, [lots[0].id])],
            'date_out': today,
            'return_by': today + timedelta(days=1),
        })
    return created


def _seed_old_gold(env, partner):
    intake = env['jewellery.old.gold'].create({
        'partner_id': partner.id if partner else False,
        'gross_weight_g': 14.300,
        'karat': '22',
        'melt_loss_pct': 2.0,
        'buyback_discount_pct': 3.0,
        'company_id': env.company.id,
    })
    intake.action_confirm()
    return intake


def post_init_hook(env):
    """Create the DEMO dataset once."""
    parameters = env['ir.config_parameter'].sudo()
    if parameters.get_param(MARKER) == '1':
        _logger.info('DEMO seed: already present, nothing to do')
        return

    rate, maker, checker = _seed_rate(env)
    products = _seed_products(env)
    lots = _seed_pieces(env, products)
    on_hand = _put_pieces_in_stock(env, lots)
    clients = _seed_clients(env, checker, lots)
    intake = _seed_old_gold(env, clients[0] if clients else None)

    # Price one piece so the log proves the engine ran off the approved rate.
    priced = lots[0].get_price_breakdown() if lots else {}

    env['jewellery.owner.card'].refresh()
    cards = env['jewellery.owner.card'].search_count([('state', '=', 'open')])

    parameters.set_param(MARKER, '1')
    _logger.info(
        'DEMO seed complete: rate %.2f/g (approved by %s), %s products, '
        '%s pieces (%s on hand), %s clients, old-gold %s valued %.2f, '
        'sample piece total %.2f, %s owner cards',
        rate.rate_per_gram, checker.login, len(products), len(lots), on_hand,
        len(clients), intake.name, intake.value, priced.get('total', 0.0), cards)
