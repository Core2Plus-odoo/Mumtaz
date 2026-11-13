"""Build the DEMO dataset.

Synthetic data only. Everything is prefixed "DEMO" so it is obvious in the
UI that nothing here is real. Idempotent: a marker parameter stops a second
install from duplicating the records.
"""
import base64
import logging
import os
from datetime import timedelta

from odoo import fields

_logger = logging.getLogger(__name__)

MARKER = 'mumtaz_jewellery_demo.seeded'

# 24K per gram, in the company currency. A round, obviously-synthetic figure.
# A believable 24K rate, not a round 100. A demonstration where every
# figure is a suspiciously neat multiple teaches the viewer nothing
# about whether the arithmetic is real.
DEMO_RATE_PER_GRAM = 245.80

PRODUCTS = [
    # name, karat, wastage %, making type, making value, category
    ('DEMO Bangle 22K', '22', 2.0, 'percent', 10.0, 'bangle'),
    ('DEMO Chain 21K', '21', 1.5, 'per_gram', 12.5, 'chain'),
    ('DEMO Ring 18K with stones', '18', 1.0, 'fixed', 250.0, 'ring'),
    ('DEMO Necklace set 21K', '21', 2.5, 'percent', 14.0, 'set'),
    ('DEMO Earrings 18K', '18', 1.0, 'fixed', 180.0, 'earrings'),
    ('DEMO Bracelet 22K', '22', 1.8, 'per_gram', 11.0, 'bracelet'),
    ('DEMO Pendant 18K with stone', '18', 1.0, 'fixed', 220.0, 'pendant'),
    ('DEMO Coin 24K', '24', 0.0, 'fixed', 40.0, 'coin'),
]

PIECES = [
    # product index, serial, gross g, stone g, stones value, rfid, certificate
    (0, 'DEMO-BNG-0001', 24.500, 0.0, 0.0, 'DEMO-RFID-0001', ''),
    (0, 'DEMO-BNG-0002', 31.200, 0.0, 0.0, 'DEMO-RFID-0002', ''),
    (0, 'DEMO-BNG-0003', 18.900, 0.0, 0.0, 'DEMO-RFID-0007', ''),
    (0, 'DEMO-BNG-0004', 27.650, 0.0, 0.0, 'DEMO-RFID-0008', ''),
    (0, 'DEMO-BNG-0005', 35.400, 0.0, 0.0, 'DEMO-RFID-0009', ''),
    (1, 'DEMO-CHN-0001', 18.750, 0.0, 0.0, 'DEMO-RFID-0003', ''),
    (1, 'DEMO-CHN-0002', 42.100, 0.0, 0.0, 'DEMO-RFID-0004', ''),
    (1, 'DEMO-CHN-0003', 26.300, 0.0, 0.0, 'DEMO-RFID-0010', ''),
    (1, 'DEMO-CHN-0004', 11.450, 0.0, 0.0, 'DEMO-RFID-0011', ''),
    (1, 'DEMO-CHN-0005', 33.800, 0.0, 0.0, 'DEMO-RFID-0012', ''),
    (2, 'DEMO-RNG-0001', 6.400, 1.1, 1800.0, 'DEMO-RFID-0005', 'DEMO-CERT-55121'),
    (2, 'DEMO-RNG-0002', 7.900, 1.6, 2600.0, 'DEMO-RFID-0006', 'DEMO-CERT-55122'),
    (2, 'DEMO-RNG-0003', 5.200, 0.8, 1450.0, 'DEMO-RFID-0013', 'DEMO-CERT-55123'),
    (2, 'DEMO-RNG-0004', 9.100, 2.4, 4100.0, 'DEMO-RFID-0014', 'DEMO-CERT-55124'),
    (2, 'DEMO-RNG-0005', 4.750, 0.6, 980.0, 'DEMO-RFID-0015', 'DEMO-CERT-55125'),
    (2, 'DEMO-RNG-0006', 11.300, 3.2, 6400.0, 'DEMO-RFID-0016', 'DEMO-CERT-55126'),
]


def _more_pieces():
    """Forty-odd more pieces across the newer designs, deterministic, so the
    lists look like a shop rather than a test fixture."""
    out = []
    n = 17
    specs = [  # product index, prefix, count, base gross, step, stone g, stones value
        (0, 'BNG', 7, 20.0, 1.7, 0.0, 0.0),
        (1, 'CHN', 7, 14.0, 3.1, 0.0, 0.0),
        (3, 'SET', 6, 48.0, 6.5, 0.0, 0.0),
        (4, 'EAR', 7, 4.2, 0.6, 0.4, 700.0),
        (5, 'BRC', 6, 16.5, 2.2, 0.0, 0.0),
        (6, 'PND', 6, 3.8, 0.5, 0.3, 550.0),
        (7, 'CON', 5, 8.0, 8.0, 0.0, 0.0),
    ]
    for idx, prefix, count, base, step, stone, stones_value in specs:
        for i in range(count):
            gross = round(base + step * i, 3)
            cert = 'DEMO-CERT-%d' % (56000 + n) if stone else ''
            out.append((idx, 'DEMO-%s-%04d' % (prefix, i + 1 + (5 if prefix in ('BNG', 'CHN') else 0)),
                        gross, stone, stones_value * (1 + i * 0.15) if stone else 0.0, 'DEMO-RFID-%04d' % n, cert))
            n += 1
    return out


PIECES = PIECES + _more_pieces()

CLIENTS = [
    # name, tier, preferred karats, typical budget, occasion kind, days ahead
    ('DEMO Client Alpha', 'standard', '22', 4000.0, 'birthday', 30),
    ('DEMO Client Bravo', 'preferred', '22,21', 12000.0, 'anniversary', 14),
    ('DEMO Client Charlie', 'private', '21', 45000.0, 'wedding', 21),
    ('DEMO Client Delta', 'royal', '22', 150000.0, 'eid', 40),
]

# Fictional people for the demo shop. The names are invented; every record
# carries a DEMO reference and a comment saying so.
MORE_CLIENTS = [
    ('Mariam Al Sayegh', 'preferred', '22', 9500.0, 'birthday', 9, 'Dubai', 'ar_001', False),
    ('Hessa Al Mansoori', 'standard', '21', 3200.0, 'eid', 35, 'Abu Dhabi', 'ar_001', False),
    ('Noura Bin Haider', 'preferred', '22,24', 18000.0, 'anniversary', 5, 'Sharjah', 'ar_001', False),
    ('Reem Al Qasimi', 'private', '21,22', 60000.0, 'wedding', 48, 'Sharjah', 'ar_001', False),
    ('Latifa Al Falasi', 'standard', '18', 2600.0, 'birthday', 62, 'Dubai', 'en_US', True),
    ('Aisha Al Ketbi', 'standard', '22', 4100.0, 'national_day', 20, 'Al Ain', 'ar_001', False),
    ('Fatima Al Shamsi', 'preferred', '21', 11000.0, 'eid', 33, 'Abu Dhabi', 'ar_001', False),
    ('Shamsa Al Suwaidi', 'standard', '22', 3800.0, 'anniversary', 71, 'Dubai', 'en_US', False),
    ('Maha Al Zaabi', 'standard', '18,21', 5200.0, 'birthday', 12, 'Ajman', 'ar_001', False),
    ('Alya Al Marri', 'preferred', '22', 14500.0, 'wedding', 27, 'Dubai', 'ar_001', False),
    ('Salama Al Nuaimi', 'standard', '21', 2900.0, 'eid', 36, 'Ras Al Khaimah', 'ar_001', True),
    ('Dana Al Hashimi', 'standard', '18', 3300.0, 'birthday', 44, 'Dubai', 'en_US', False),
    ('Sara Khalil', 'standard', '21', 2400.0, 'anniversary', 17, 'Dubai', 'en_US', False),
    ('Lina Haddad', 'preferred', '18,21', 8700.0, 'birthday', 23, 'Abu Dhabi', 'en_US', False),
    ('Yasmin Nasser', 'standard', '22', 4600.0, 'eid', 38, 'Dubai', 'en_US', False),
    ('Hanan Saleh', 'standard', '21', 3100.0, 'birthday', 55, 'Sharjah', 'ar_001', False),
    ('Rania Khoury', 'preferred', '18', 7600.0, 'anniversary', 8, 'Dubai', 'en_US', False),
    ('Nadia Farouk', 'standard', '21,22', 3900.0, 'wedding', 90, 'Abu Dhabi', 'ar_001', False),
    ('Zainab Hussain', 'standard', '22', 2800.0, 'eid', 34, 'Dubai', 'en_US', False),
    ('Amal Rahman', 'standard', '21', 2200.0, 'birthday', 26, 'Ajman', 'en_US', True),
    ('Huda Mahmoud', 'preferred', '22', 10500.0, 'diwali', 19, 'Dubai', 'en_US', False),
    ('Priya Menon', 'standard', '22', 3600.0, 'diwali', 19, 'Dubai', 'en_US', False),
    ('Anjali Nair', 'preferred', '22,24', 12800.0, 'wedding', 41, 'Abu Dhabi', 'en_US', False),
    ('Meera Pillai', 'standard', '22', 2700.0, 'birthday', 66, 'Sharjah', 'en_US', False),
    ('Kavya Reddy', 'standard', '18,22', 4300.0, 'diwali', 19, 'Dubai', 'en_US', False),
    ('Farah Al Thani', 'private', '22', 85000.0, 'eid', 37, 'Doha', 'ar_001', False),
    ('Mozah Al Kuwari', 'preferred', '21,22', 16000.0, 'national_day', 29, 'Doha', 'ar_001', False),
    ('Ghada Al Harthi', 'standard', '21', 3500.0, 'birthday', 15, 'Muscat', 'ar_001', False),
    ('Lamia Al Saud', 'royal', '22,24', 220000.0, 'wedding', 52, 'Riyadh', 'ar_001', False),
    ('Jawaher Al Otaibi', 'preferred', '21', 13200.0, 'eid', 35, 'Riyadh', 'ar_001', False),
    ('Wafa Al Dossari', 'standard', '22', 4800.0, 'anniversary', 11, 'Dammam', 'ar_001', False),
    ('Elena Petrova', 'standard', '18', 3000.0, 'birthday', 24, 'Dubai', 'en_US', False),
    ('Sophie Laurent', 'preferred', '18', 9100.0, 'anniversary', 31, 'Dubai', 'en_US', False),
    ('Chen Wei', 'standard', '24', 5600.0, 'other', 58, 'Dubai', 'en_US', False),
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


def _design_image(category, kind='jpg'):
    """The demo photo (or the try-on cutout) for a design, shipped with the
    module; None if absent."""
    name = '%s.jpg' % category if kind == 'jpg' else '%s-cutout.png' % category
    path = os.path.join(os.path.dirname(__file__), 'static', 'img', name)
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as fh:
        return base64.b64encode(fh.read())


# Physical size per demo design, for the try-on to draw at true scale and
# judge fit: (width of the cutout mm, length mm, inner diameter mm).
DIMS = {
    'bangle': (66, None, 63.0), 'chain': (120, 450, None), 'ring': (20, None, 17.3), 'set': (160, 420, None),
    'earrings': (12, None, None), 'bracelet': (60, 180, None), 'pendant': (28, 450, None), 'coin': (28, None, None),
}


def _dims(category):
    width, length, inner = DIMS.get(category, (None, None, None))
    return {'jewellery_width_mm': width or 0.0, 'jewellery_length_mm': length or 0.0, 'jewellery_inner_diameter_mm': inner or 0.0}


def _seed_products(env):
    template = env['product.template']
    storable = 'is_storable' in template._fields
    products = []
    for name, karat, wastage, making_type, making_value, category in PRODUCTS:
        existing = template.search([('name', '=', name)], limit=1)
        if existing:
            if not existing.jewellery_category:
                existing.jewellery_category = category
            if not existing.image_1920 and _design_image(category):
                existing.image_1920 = _design_image(category)
            if not existing.jewellery_tryon_image and _design_image(category, 'cutout'):
                existing.jewellery_tryon_image = _design_image(category, 'cutout')
            if not existing.jewellery_width_mm:
                existing.write(_dims(category))
            products.append(existing)
            continue
        values = {
            'name': name,
            'is_jewellery': True,
            'jewellery_category': category,
            'tracking': 'serial',
            'jewellery_karat': karat,
            'jewellery_wastage_pct': wastage,
            'jewellery_making_type': making_type,
            'jewellery_making_value': making_value,
        }
        image = _design_image(category)
        if image:
            values['image_1920'] = image
        cutout = _design_image(category, 'cutout')
        if cutout:
            values['jewellery_tryon_image'] = cutout
        values.update(_dims(category))
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
        existing = lots.search([('name', '=', serial)], limit=1)
        if existing:
            created |= existing
            continue
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


def _align_demo_vat(env, products):
    """One VAT figure for the whole demo.

    The pricing engine reads mumtaz_jewellery.vat_rate (5) for the breakdown
    a client sees at the counter; Odoo's tax engine owns the tax on the
    invoice and uses the company's default sale tax, which on a fresh
    database is whatever the localisation shipped (15% on the first VPS
    demo). Two VAT figures on one receipt is the first thing a finance
    manager would catch. The demo sets both to 5%; a real tenant's finance
    manager confirms the rate and the tax (docs/mumtaz-jewel/CLAUDE.md).
    """
    params = env['ir.config_parameter'].sudo()
    params.set_param('mumtaz_jewellery.vat_rate', '5')
    Tax = env['account.tax']
    tax = Tax.search([('company_id', '=', env.company.id), ('type_tax_use', '=', 'sale'),
                      ('amount_type', '=', 'percent'), ('amount', '=', 5.0)], limit=1)
    if not tax:
        tax = Tax.create({'name': 'VAT 5%', 'type_tax_use': 'sale', 'amount_type': 'percent',
                          'amount': 5.0, 'company_id': env.company.id})
    env.company.account_sale_tax_id = tax
    for product in products:
        product.taxes_id = [(6, 0, [tax.id])]
    return tax


def _seed_cost_basis(lots):
    """A recorded cost per piece, so margin has something to be measured
    against. Synthetic: metal at the approved rate plus a fraction of the
    making charge. A real tenant records what it actually paid at intake."""
    for lot in lots:
        breakdown = lot.get_price_breakdown()
        lot.jewellery_cost_value = round(
            breakdown['metal_value'] + 0.6 * breakdown['making_charge']
            + breakdown['stones_value'] * 0.8, 2)


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
        existing = partners.search([('name', '=', name)], limit=1)
        if existing:
            created |= existing
            continue
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

    for i, (name, tier, karats, budget, occasion_kind, days, city, lang, no_marketing) in enumerate(MORE_CLIENTS):
        if partners.search_count([('name', '=', name)]):
            continue
        values = {
            'name': name, 'jewellery_tier': tier, 'preferred_karats': karats, 'typical_budget': budget,
            'city': city, 'lang': lang if lang in env['res.lang'].mapped('code') else False,
            'phone': '+971 50 000 %04d' % (1000 + i), 'no_marketing': no_marketing,
            'ref': 'DEMO-C-%03d' % (i + 5),
            'taste_notes': 'DEMO record. Synthetic preferences for the demo only.',
            'comment': 'DEMO data: a fictional client, not a real person.',
        }
        if tier in ('private', 'royal'):
            values['relationship_manager_id'] = manager.id
        partner = partners.create(values)
        env['jewellery.occasion'].create({
            'partner_id': partner.id, 'kind': occasion_kind, 'date': today + timedelta(days=days),
            'recurring': True, 'lead_days': 21, 'note': 'DEMO occasion.',
        })
        created |= partner

    # One piece out on approval, due back shortly, so the owner screen and the
    # memo reminder have something to show.
    if created and lots and not env['jewellery.approval.memo'].search_count([('partner_id', '=', created[1].id)]):
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


def _seed_sales(env, clients, lots):
    """Leave real documents behind: a quotation, a confirmed order and a
    posted invoice.

    Every figure is produced by the pricing engine from the approved rate --
    the same path a shop uses -- so a demonstration can open any line and
    show where the number came from. Nothing here types a price.
    """
    if not clients or len(lots) < 4:
        return {}

    Sale = env['sale.order']
    product_of = {lot.id: lot.product_id.id for lot in lots}
    # The hook runs as the system user, so the orders' salesperson would be
    # OdooBot. The Quotations menu opens on "My Quotations" by default, and
    # a presenter logged in as admin would see an empty screen. Make admin
    # the salesperson so the documents appear where the demo looks for them.
    presenter = env.ref('base.user_admin', raise_if_not_found=False)

    def order_for(partner, lot, discount=0.0):
        order = Sale.create({
            'partner_id': partner.id,
            'user_id': presenter.id if presenter else False,
            'order_line': [(0, 0, {
                'product_id': product_of[lot.id],
                'product_uom_qty': 1,
                'jewellery_lot_id': lot.id,
                'jewellery_making_discount_pct': discount,
            })],
        })
        # Priced as the presenter -- a jewellery manager -- because the demo's
        # 15% dealer discount is above the staff ceiling, as it would be in a shop.
        pricer = order.order_line[0].with_user(presenter) if presenter else order.order_line[0]
        pricer.action_price_from_rate()
        return order

    out = {}

    # 1. A quotation still open, so the "Price from gold rate" button and a
    #    live breakdown are there to show.
    quote = order_for(clients[0], lots[2])
    out['quotation'] = quote.name

    # 2. A confirmed order: the price is now frozen. This is the one to open
    #    when explaining why a rate change tomorrow cannot move it.
    confirmed = order_for(clients[1], lots[6])
    confirmed.action_confirm()
    out['order'] = confirmed.name

    # 3. A posted invoice carrying the full breakdown, with a dealer discount
    #    on the making charge only -- the metal is never discounted.
    billed = order_for(clients[2], lots[10], discount=15.0)
    billed.action_confirm()
    invoice = billed._create_invoices()
    invoice.action_post()
    out['invoice'] = invoice.name
    out['invoice_total'] = invoice.amount_total

    return out


def _grant_presenter(env):
    """Let the demo presenter see the whole product.

    The presenter signs in as admin. Being an Odoo administrator grants the
    Settings app, not the jewellery groups, so without this the owner's
    screens, memos and the Private/Royal clients are invisible to the very
    person giving the demonstration -- the Jawhar API returned 403 on the
    owner summary for admin, which is how this was found. Demo database
    only; a real tenant assigns these groups to named people.
    """
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if not admin:
        return
    groups = env.ref('mumtaz_jewellery.group_jewellery_manager') | \
        env.ref('mumtaz_jewellery_vip.group_vip_manager')
    admin.write({_user_groups_field(env): [(4, g.id) for g in groups]})


def _seed_pipeline(env, clients, lots, presenter):
    """Something on the Pipeline screen: an enquiry, a shared tray, a tray
    with a viewing requested. Synthetic, and the link tokens are not kept."""
    if len(clients) < 3 or len(lots) < 6:
        return {}
    Tray = env['jewellery.tray'].with_user(presenter) if presenter else env['jewellery.tray']
    # Only pieces that are actually offerable: not the ones the sales seed sold
    # or put on approval, and not whatever a demo walk sold since. Chosen by
    # eligibility, not by index, so the seed never trips over its own data.
    eligible = Tray._eligible_lots().sorted('name')
    rings = eligible.filtered(lambda l: l.karat == '18')[:1] or eligible[:1]
    chains = (eligible - rings)[:2]
    if not rings or len(chains) < 2:
        return {}
    out = {}
    # Alpha: an enquiry only, chosen by hand
    alpha = Tray.create({'partner_id': clients[0].id, 'intent': 'birthday'})
    alpha.action_add_piece(rings[0], reasons='Asked about an 18K ring on her last visit')
    out['enquiry'] = alpha.name
    # Bravo: ranked and shared
    bravo = Tray.create({'partner_id': clients[1].id, 'intent': 'anniversary'})
    bravo.action_build(limit=3)
    bravo.action_share()
    out['shared'] = bravo.name
    # Charlie (Private): chosen by hand, shared, a viewing requested
    charlie = Tray.create({'partner_id': clients[2].id, 'intent': 'wedding'})
    for lot in chains:
        charlie.action_add_piece(lot, reasons='Chosen by the relationship manager')
    charlie.action_share()
    charlie._public_feedback(charlie.line_ids[0].public_ref, 'like')
    charlie._public_request_viewing('Thursday afternoon', 'with my mother')
    out['viewing'] = charlie.name
    return out


def _seed_consent(env):
    """Consent recorded on most demo clients (they are fictional); a few
    left unrecorded and the do-not-contact ones withdrawn, so the Outreach
    screen shows every case. Nothing twice."""
    Partner = env['res.partner']
    if 'marketing_consent' not in Partner._fields:
        return 0
    done = 0
    clients = Partner.search([('comment', 'ilike', 'DEMO data'), ('marketing_consent', '=', 'unknown')], order='id')
    presenter = env.ref('base.user_admin', raise_if_not_found=False)
    for i, p in enumerate(clients):
        if p.no_marketing:
            status, source = 'withdrawn', 'phone'
        elif i % 5 == 4:
            continue  # left unrecorded on purpose
        else:
            status, source = 'given', ('in_store', 'form', 'phone')[i % 3]
        p.with_user(presenter).action_record_consent(status, source=source, note='DEMO consent record.')
        done += 1
    return done


def _seed_kyc(env):
    """Identity and screening on a few demo clients (fictional): verified
    documents, one expiring soon, one screening match left open so the
    counter's refusal can be shown. The cash threshold is NOT seeded: it is
    a compliance value the named finance manager confirms on the
    Compliance screen, never a demo default."""
    Partner = env['res.partner']
    if 'kyc_status' not in Partner._fields:
        return 0
    # A cash register, so the counter can take cash and the threshold has
    # something to compare with. The demo database has no chart of accounts
    # and therefore no cash journal of its own.
    Journal = env['account.journal']
    if not Journal.search([('type', '=', 'cash'), ('company_id', '=', env.company.id)], limit=1):
        Journal.create({'name': 'Cash register', 'type': 'cash', 'code': 'CSH1', 'company_id': env.company.id})
    today = fields.Date.context_today(Partner)
    presenter = env.ref('base.user_admin', raise_if_not_found=False)
    plan = [('DEMO Client Alpha', 'emirates_id', 'A1B2', 900, None),
            ('DEMO Client Bravo', 'passport', 'Z9Y8', 20, None),
            ('Mariam Al Sayegh', 'emirates_id', '4K7Q', 400, None),
            ('Noura Bin Haider', 'emirates_id', '7M2P', 1200, None),
            ('Huda Mahmoud', 'passport', 'H3LD', 600, 'match'),
            ('Chen Wei', 'passport', 'CW01', 300, 'clear')]
    done = 0
    for name, doc, last4, days, screening in plan:
        p = Partner.search([('name', '=', name), ('kyc_status', '=', 'none')], limit=1)
        if not p:
            continue
        p.with_user(presenter).action_verify_identity(doc, last4, today + timedelta(days=days), note='DEMO document check (synthetic).')
        if screening:
            p.with_user(presenter).action_record_screening(screening, risk_band='high' if screening == 'match' else 'low',
                                                           note='DEMO screening (synthetic, not a real list).')
        done += 1
    return done


def _seed_stores(env):
    """A second boutique with eight pieces received by transfer, one transfer
    still on the road for three days (an exception), and today's
    reconciliation at the first store with one piece not found. Nothing
    twice."""
    W = env['stock.warehouse']
    if 'jewellery_store_limit_fine_g' not in W._fields:
        return {}
    first = W.search([('company_id', '=', env.company.id)], order='id', limit=1)
    second = W.search([('code', '=', 'BTQ2')], limit=1)
    if not second:
        second = W.create({'name': 'Boutique 2 (Abu Dhabi)', 'code': 'BTQ2', 'company_id': env.company.id})
        second.jewellery_store_limit_fine_g = 400.0
    out = {}
    Transfer = env['jewellery.transfer'].sudo()
    presenter = env.ref('base.user_admin', raise_if_not_found=False)
    Transfer = Transfer.with_user(presenter) if presenter else Transfer
    if not Transfer.search_count([]):
        shelf = env['jewellery.tray']._eligible_lots().filtered(lambda l: l.jewellery_store() == first).sorted('name')
        if len(shelf) >= 12:
            t1 = Transfer.create({'from_warehouse_id': first.id, 'to_warehouse_id': second.id,
                                  'lot_ids': [(6, 0, shelf[:8].ids)], 'note': 'DEMO: opening stock for Boutique 2.'})
            t1.action_dispatch()
            t1.action_receive()
            t2 = Transfer.create({'from_warehouse_id': first.id, 'to_warehouse_id': second.id,
                                  'lot_ids': [(6, 0, shelf[8:10].ids)], 'note': 'DEMO: on the road.'})
            t2.action_dispatch()
            t2.sudo().write({'dispatched_at': fields.Datetime.now() - timedelta(days=3)})
            out['received'] = t1.name
            out['in_transit'] = t2.name
    Recon = env['jewellery.gold.reconciliation'].sudo()
    today = fields.Date.context_today(env['res.partner'])
    if not Recon.search_count([('warehouse_id', '=', first.id), ('date', '=', today)]):
        rec = Recon.open_for(first)
        serials = rec.line_ids.mapped('lot_id.name')
        rec.action_count(serials[1:])          # one piece not found: a variance to show
        out['reconciliation'] = rec.name
    return out


def _seed_channels(env):
    """A rate feed on the fixture provider, read once: it leaves a DRAFT
    gold rate for a person to approve, which is the point. One design taken
    off the web shelf. Nothing twice."""
    Feed = env['jewellery.rate.feed'] if 'jewellery.rate.feed' in env else None
    if Feed is None:
        return {}
    out = {}
    feed = Feed.search([('company_id', '=', env.company.id)], limit=1)
    if not feed:
        feed = Feed.create({'name': 'DEMO gold feed (fixture)', 'provider': 'fixture', 'fixture_value': 247.15,
                            'unit': 'gram_24k', 'company_id': env.company.id})
        res = feed.action_fetch()
        out['feed_draft'] = res['rate'].rate_per_gram if res.get('rate') else '-'
    coin = env['product.template'].search([('is_jewellery', '=', True), ('jewellery_category', '=', 'coin')], limit=1)
    if coin and coin.jewellery_published:
        coin.jewellery_published = False
        out['unpublished'] = coin.name
    return out


def _seed_client_app(env):
    """DEMO ONLY: the client app echoes the sign-in code in its answer, so a
    demo can sign in without a person in the loop. A real tenant keeps the
    parameter at 0 and a person gives the client her code."""
    if 'jewellery.client.session' not in env:
        return False
    env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.client_code_echo', '1')
    # The first demo clients predate phones on the record; the app signs in
    # by phone, so give the one with purchases a synthetic number.
    alpha = env['res.partner'].search([('name', '=', 'DEMO Client Alpha'), ('phone', '=', False)], limit=1)
    if alpha:
        alpha.phone = '+971 50 000 0001'
    return True


def _seed_outreach(env, presenter):
    """Layla drafts the occasion messages due, for a person to review: the
    Outreach screen opens with work on it. One per occasion per year."""
    Agent = env['jewellery.ai.agent']
    if not hasattr(Agent, 'outreach_prepare'):
        return 0
    Agent = Agent.with_user(presenter) if presenter else Agent
    out = Agent.outreach_prepare()
    return 0 if out.get('refused') else out['count']


def _seed_agents(env, clients, presenter):
    """Something in the approvals inbox and the audit: Layla's follow-up for
    the standard client, a refused request for the Private one (the control
    working), and Zayan's brief. All local paths; no model is called."""
    if len(clients) < 3:
        return {}
    Agent = env['jewellery.ai.agent'].with_user(presenter) if presenter else env['jewellery.ai.agent']
    out = {}
    fu = Agent.draft_followup(clients[1], note='She liked the bangle on Saturday.')
    if not fu.get('refused'):
        out['followup'] = fu['draft'].name
    refused = Agent.prepare_tray(clients[2])
    out['refused'] = refused.get('refused') or '-'
    Agent.brief()
    return out


def top_up(env):
    """A database seeded by an earlier version gets the designs, pieces
    and clients added since, by name, nothing twice. Safe to run again."""
    products = _seed_products(env)
    lots = _seed_pieces(env, products)
    # Only pieces that are new to this database go on the shelf: a piece the
    # demo sold must stay sold.
    fresh = lots.filtered(lambda l: not l.product_qty and not l.jewellery_cost_value)
    on_hand = _put_pieces_in_stock(env, fresh) if fresh else 0
    _seed_cost_basis(fresh)
    manager = env['res.users'].search([('login', '=', 'demo_rate_checker')], limit=1) or env.ref('base.user_admin')
    clients = _seed_clients(env, manager, lots)
    kiosk = _seed_kiosk(env)
    presenter = env.ref('base.user_admin', raise_if_not_found=False)
    consent = _seed_consent(env)
    outreach = _seed_outreach(env, presenter)
    _seed_kyc(env)
    _seed_stores(env)
    _seed_channels(env)
    _seed_client_app(env)
    _logger.info('DEMO top-up: %s products, %s pieces (%s on hand), %s clients, kiosk %s, consent %s, outreach drafts %s',
                 len(products), len(lots), on_hand, len(clients), '/'.join(kiosk.values()) or '-', consent, outreach)
    return {'products': len(products), 'pieces': len(lots), 'clients': len(clients), 'consent': consent, 'outreach': outreach}


def _seed_kiosk(env):
    """Two requests from the kiosk waiting for a person: a viewing and a
    next-day delivery. Fictional callers; nothing is reserved."""
    Req = env['jewellery.kiosk.request']
    if Req.search_count([]):
        return {}
    eligible = env['jewellery.tray']._eligible_lots().sorted('name')
    if len(eligible) < 2:
        return {}
    out = {}
    out['viewing'] = Req.create_public('viewing', eligible[-1].name, 'Walk-in Hind', '+971500009001',
                                       preferred_time='Thursday after 6', note='Saw it in the window.', lang='en')['reference']
    out['delivery'] = Req.create_public('delivery', eligible[-2].name, 'Online Sumaya', '+971500009002',
                                        address='Villa 12, Street 4, Jumeirah 1, Dubai', slot='afternoon',
                                        note='Gift, please wrap.', lang='ar', channel='web')['reference']
    return out


def post_init_hook(env):
    """Create the DEMO dataset once."""
    parameters = env['ir.config_parameter'].sudo()
    if parameters.get_param(MARKER) == '1':
        top_up(env)
        return

    _grant_presenter(env)
    # Quotations hold their rate for this many days, then must be renewed at
    # the current approved rate. The owner's demo value; a tenant sets its own
    # in Sales settings (standard Odoo field on the company).
    env.company.quotation_validity_days = 7
    rate, maker, checker = _seed_rate(env)
    products = _seed_products(env)
    _align_demo_vat(env, products)
    lots = _seed_pieces(env, products)
    on_hand = _put_pieces_in_stock(env, lots)
    _seed_cost_basis(lots)
    clients = _seed_clients(env, checker, lots)
    intake = _seed_old_gold(env, clients[0] if clients else None)
    docs = _seed_sales(env, clients, lots)
    presenter = env.ref('base.user_admin', raise_if_not_found=False)
    pipeline = _seed_pipeline(env, clients, lots, presenter)
    agents = _seed_agents(env, clients, presenter)
    kiosk = _seed_kiosk(env)
    consent = _seed_consent(env)
    outreach = _seed_outreach(env, presenter)
    kyc = _seed_kyc(env)
    stores = _seed_stores(env)
    _seed_channels(env)
    _seed_client_app(env)

    # Price one piece so the log proves the engine ran off the approved rate.
    priced = lots[0].get_price_breakdown() if lots else {}

    env['jewellery.owner.card'].refresh()
    cards = env['jewellery.owner.card'].search_count([('state', '=', 'open')])

    parameters.set_param(MARKER, '1')
    _logger.info(
        'DEMO seed complete: rate %.2f/g (approved by %s), %s products, '
        '%s pieces (%s on hand), %s clients, old-gold %s valued %.2f, '
        'sample piece total %.2f, %s owner cards, '
        'quotation %s, order %s, invoice %s (%.2f), trays %s, '
        'AI drafts %s (refused: %s), kiosk requests %s, consent on %s clients, outreach drafts %s, identity verified on %s, stores %s',
        rate.rate_per_gram, checker.login, len(products), len(lots), on_hand,
        len(clients), intake.name, intake.value, priced.get('total', 0.0),
        cards, docs.get('quotation', '-'), docs.get('order', '-'),
        docs.get('invoice', '-'), docs.get('invoice_total', 0.0),
        '/'.join(pipeline.values()) or '-',
        agents.get('followup', '-'), agents.get('refused', '-'), '/'.join(kiosk.values()) or '-', consent, outreach, kyc, '/'.join(stores.values()) or '-')
