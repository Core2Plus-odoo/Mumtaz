# ─────────────────────────────────────────────────────────────────────────────
# C2P Consultants — Odoo 19 setup PASS 2: quotation templates + doc branding.
# Run: odoo shell -d Mumtaz_C2P < ops/deployment/c2p_setup_2.py
# Idempotent & defensive (safe to re-run; independent sections).
# ─────────────────────────────────────────────────────────────────────────────
def _log(m): print("  " + m)

def prod(name):
    """Find a sellable product.product by its (template) name."""
    return env['product.product'].search([('name', '=', name)], limit=1)

# ── 1. Quotation templates ───────────────────────────────────────────────────
print("1) Quotation templates")
TERMS = ("Prices are in AED and exclusive of 5% VAT unless stated.\n"
         "Quotation valid for 30 days. Payment terms as agreed on the order.\n"
         "C2P Consultants FZC LLC.")

TEMPLATES = [
    ("Odoo ERP Implementation - Proposal", [
        ("ERP Discovery & BRD", 1),
        ("Odoo ERP Implementation", 1),
        ("Training", 2),
    ]),
    ("Annual Support & AMC", [
        ("Odoo Support & AMC (monthly)", 12),
    ]),
    ("Advisory Retainer", [
        ("Finance & VAT Advisory", 10),
        ("UAE VAT Compliance (FTA) - Retainer", 1),
    ]),
    ("Custom Development", [
        ("Odoo Customization & Development", 10),
    ]),
]

if 'sale.order.template' not in env:
    _log("✗ sale.order.template not available (is sale_management installed?)")
else:
    SOT = env['sale.order.template']
    line_field = ('sale_order_template_line_ids'
                  if 'sale_order_template_line_ids' in SOT._fields
                  else 'sale_order_line_ids')
    for tname, lines in TEMPLATES:
        try:
            if SOT.search([('name', '=', tname)], limit=1):
                _log("• %s (exists)" % tname)
                continue
            line_cmds = []
            missing = []
            for pname, qty in lines:
                p = prod(pname)
                if not p:
                    missing.append(pname)
                    continue
                lv = {'product_id': p.id, 'product_uom_qty': qty, 'name': pname}
                line_cmds.append((0, 0, lv))
            vals = {'name': tname, line_field: line_cmds}
            if 'number_of_days' in SOT._fields:
                vals['number_of_days'] = 30
            if 'note' in SOT._fields:
                vals['note'] = TERMS
            SOT.create(vals)
            _log("＋ %s%s" % (tname, ("  (skipped missing: %s)" % ", ".join(missing)) if missing else ""))
        except Exception as e:
            _log("✗ %s → %s" % (tname, str(e)[:140]))

# ── 2. Document branding (footer on quotes/invoices) ─────────────────────────
print("2) Document branding")
try:
    company = env.company
    updates = {}
    if 'report_footer' in company._fields:
        updates['report_footer'] = ("C2P Consultants FZC LLC · core2plus.com · "
                                     "End-to-end Odoo ERP, advisory & compliance")
    # Nudge the layout to a modern template if none is set.
    if 'external_report_layout_id' in company._fields and not company.external_report_layout_id:
        layout = env.ref('web.external_layout_standard', raise_if_not_found=False)
        if layout:
            updates['external_report_layout_id'] = layout.id
    if updates:
        company.write(updates)
        _log("footer + layout set for %s" % company.name)
    else:
        _log("nothing to update (already branded)")
except Exception as e:
    _log("✗ branding → %s" % str(e)[:140])

env.cr.commit()
print("\n✓ Pass 2 committed. Quotation templates are under Sales → Configuration → "
      "Quotation Templates; branding shows on quote/invoice PDFs.")
