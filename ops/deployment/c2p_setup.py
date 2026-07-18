# ─────────────────────────────────────────────────────────────────────────────
# C2P Consultants — Odoo 19 setup (run via: odoo shell -d Mumtaz_C2P)
# Idempotent & defensive: each section is independent; re-running is safe.
# ─────────────────────────────────────────────────────────────────────────────
def _log(m): print("  " + m)

# 5% UAE sale/purchase taxes (from l10n_ae), and common UoMs
sale_tax = env['account.tax'].search(
    [('type_tax_use', '=', 'sale'), ('amount', '=', 5)], limit=1)
uom = {}
for key, xmlid in (('unit', 'uom.product_uom_unit'),
                   ('hour', 'uom.product_uom_hour'),
                   ('day',  'uom.product_uom_day')):
    try:
        uom[key] = env.ref(xmlid)
    except Exception:
        uom[key] = env['uom.uom'].search([], limit=1)

# ── 1. Product categories (C2P divisions) ────────────────────────────────────
print("1) Product categories")
Categ = env['product.category']
cats = {}
for name in ('C2P Consultants', 'C2P Solutions', 'C2P Ventures'):
    c = Categ.search([('name', '=', name)], limit=1) or Categ.create({'name': name})
    cats[name] = c
    _log(name)

# ── 2. Service catalog ───────────────────────────────────────────────────────
print("2) Services")
Tmpl = env['product.template']
SERVICES = [
    # name, category, price, uom, invoice_policy
    ("ERP Discovery & BRD", "C2P Consultants", 15000, 'unit', 'order'),
    ("Business Process Design & Re-engineering", "C2P Consultants", 25000, 'unit', 'order'),
    ("Finance & VAT Advisory", "C2P Consultants", 500, 'hour', 'delivery'),
    ("UAE VAT Compliance (FTA) - Retainer", "C2P Consultants", 2500, 'unit', 'order'),
    ("KSA ZATCA Compliance", "C2P Consultants", 10000, 'unit', 'order'),
    ("Process Audit & Gap Analysis", "C2P Consultants", 12000, 'unit', 'order'),
    ("Change Management Consulting", "C2P Consultants", 3500, 'day', 'delivery'),
    ("Odoo ERP Implementation", "C2P Solutions", 50000, 'unit', 'order'),
    ("Odoo Customization & Development", "C2P Solutions", 3000, 'day', 'delivery'),
    ("eCommerce Development", "C2P Solutions", 35000, 'unit', 'order'),
    ("AI Agents & Automation", "C2P Solutions", 30000, 'unit', 'order'),
    ("BI Dashboards", "C2P Solutions", 8000, 'unit', 'order'),
    ("Web & Mobile Development", "C2P Solutions", 3000, 'day', 'delivery'),
    ("Oracle APEX Application", "C2P Solutions", 3500, 'day', 'delivery'),
    ("Odoo Support & AMC (monthly)", "C2P Solutions", 3000, 'unit', 'order'),
    ("Training", "C2P Solutions", 2500, 'day', 'delivery'),
    ("Odoo Consulting (Hourly)", "C2P Solutions", 400, 'hour', 'delivery'),
]
for name, cat, price, u, pol in SERVICES:
    if Tmpl.search([('name', '=', name)], limit=1):
        continue
    vals = {'name': name, 'type': 'service', 'list_price': price,
            'sale_ok': True, 'purchase_ok': False,
            'categ_id': cats[cat].id, 'invoice_policy': pol,
            'uom_id': uom[u].id}
    try:
        vals['uom_po_id'] = uom[u].id
    except Exception:
        pass
    if sale_tax:
        vals['taxes_id'] = [(6, 0, sale_tax.ids)]
    try:
        Tmpl.create(vals)
        _log("＋ %s  (AED %s)" % (name, price))
    except Exception as e:
        _log("✗ %s → %s" % (name, str(e)[:120]))

# ── 3. CRM pipeline stages + sales team ──────────────────────────────────────
print("3) CRM pipeline")
try:
    Stage = env['crm.stage']
    for i, s in enumerate(['New', 'Qualified', 'Proposal Sent',
                           'Negotiation', 'Won']):
        if not Stage.search([('name', '=', s)], limit=1):
            Stage.create({'name': s, 'sequence': i * 10})
    Team = env['crm.team']
    if not Team.search([('name', '=', 'C2P Sales')], limit=1):
        Team.create({'name': 'C2P Sales'})
    _log("stages + C2P Sales team")
except Exception as e:
    _log("✗ CRM → %s" % str(e)[:120])

# ── 4. Project delivery-methodology stages ───────────────────────────────────
print("4) Project stages")
try:
    TT = env['project.task.type']
    for i, s in enumerate(['Discovery', 'Design', 'Build',
                           'UAT', 'Go-Live', 'Support']):
        if not TT.search([('name', '=', s)], limit=1):
            TT.create({'name': s, 'sequence': i * 10})
    _log("Discovery → Design → Build → UAT → Go-Live → Support")
except Exception as e:
    _log("✗ Project → %s" % str(e)[:120])

# ── 5. Payment terms (Net 15 / Net 30) ───────────────────────────────────────
print("5) Payment terms")
for name, days in [('Net 15', 15), ('Net 30', 30)]:
    try:
        PT = env['account.payment.term']
        if PT.search([('name', '=', name)], limit=1):
            continue
        PT.create({'name': name,
                   'line_ids': [(0, 0, {'value': 'percent', 'value_amount': 100.0,
                                        'nb_days': days})]})
        _log("＋ %s" % name)
    except Exception as e:
        _log("✗ %s → %s" % (name, str(e)[:120]))

env.cr.commit()
print("\n✓ C2P setup committed. Refresh the browser.")
