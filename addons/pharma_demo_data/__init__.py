import json
from datetime import date

from odoo import SUPERUSER_ID, api


def post_init_hook(env):
    env = api.Environment(env.cr, SUPERUSER_ID, {})
    env["ir.config_parameter"].set_param("pharma.mode", "demo")
    admin = env.ref("base.user_admin")
    env.company.write({"name": "Pharma Demo Co"})  # generic, fictional tenant name
    # Demo convenience ONLY (this module is never installed in production): let 'admin' try every role.
    admin.write({"group_ids": [(4, env.ref(f"pharma_core.{g}").id) for g in (
        "group_pharma_finance", "group_pharma_tax_approver", "group_pharma_admin")]})
    Rule, Prod, Event = env["pharma.tax.rule"], env["product.template"], env["pharma.tax.event"]

    # DEMO-rate rules: fictional percentages, refused when pharma.mode = production.
    rules = {}
    for code, ttype, rate in (("DEMO-RULE-1", "SALES_TAX_OUTPUT", 10.0), ("DEMO-RULE-2", "INCOME_TAX_153_2A", 2.0)):
        rules[code] = Rule.with_context(pharma_internal=True).create({
            "name": code, "tax_type": ttype, "tax_class": "DEMO_CLASS_X", "rate": rate,
            "date_from": date(2026, 1, 1), "legal_ref": "DEMO-LEGAL-REF", "evidence_ref": "DEMO-EVID-1",
            "is_demo": True, "state": "approved", "approved_by": admin.id, "approved_on": "2026-01-01 00:00:00"})

    def product(code, name, approved):
        vals = {"name": name, "default_code": code, "type": "consu", "list_price": 1000.0, "is_storable": True}
        p = Prod.create(vals)
        if approved:
            p.with_context(pharma_internal=True).write({
                "pharma_tax_class": "DEMO_CLASS_X", "pharma_tax_evidence_ref": "DEMO-EVID-1",
                "pharma_tax_status": "approved", "pharma_tax_approved_by": admin.id})
        return p.product_variant_id

    A = product("DEMO-SKU-A", "DEMO Wellness Product A (fictional)", True)
    B = product("DEMO-SKU-B", "DEMO Wellness Product B (fictional)", True)
    C = product("DEMO-SKU-C", "DEMO Wellness Product C (fictional, tax pending)", False)

    orders = [("DEMO-O-1001", "shopify", "COD", A, 10000, date(2026, 11, 3)),
              ("DEMO-O-1002", "shopify", "COD", A, 45000, date(2026, 11, 3)),
              ("DEMO-O-1003", "odoo_website", "COD", B, 45000, date(2026, 11, 4)),
              ("DEMO-O-1004", "shopify", "PREPAID", A, 8000, date(2026, 11, 4)),
              ("DEMO-O-1005", "odoo_website", "PREPAID", B, 12000, date(2026, 11, 5)),
              ("DEMO-O-1006", "shopify", "COD", C, 6000, date(2026, 11, 5))]
    Raw = env["pharma.raw.event"]
    for oid, ch, pay, prod, amt, d in orders:
        Raw.ingest(ch, oid, json.dumps({"order": oid, "payment": pay, "sku": prod.default_code,
                                        "total": amt, "date": str(d), "DEMO": True}), is_demo=True)
        res = env["pharma.tax.rule"].resolve(prod, d, amt, "SALES_TAX_OUTPUT")
        if res["resolution"] == "resolved":
            Event.post_event(oid, ch, f"DEMO-SET-{oid[-4:]}", "SALES_TAX_OUTPUT", prod, d, amt)
            if pay == "COD":
                Event.post_event(oid, ch, f"DEMO-SET-{oid[-4:]}", "INCOME_TAX_153_2A", prod, d, amt)

    Run, Item = env["pharma.recon.run"], env["pharma.recon.item"]
    cod = Run.create({"name": "DEMO R03 COD batch DEMO-COD-BATCH-1 (DEMO Courier A)", "run_type": "cod",
                      "period": "2026-11", "authorized_deductions": 5000.0, "is_demo": True})
    for oid, ch, pay, prod, amt, d in orders:
        if pay == "COD":
            Item.create({"run_id": cod.id, "side": "source", "item_ref": f"AWB-{oid[-4:]}",
                         "batch_ref": "DEMO-COD-BATCH-1", "amount": amt, "item_date": d,
                         "source_label": "DEMO Courier A statement",
                         "raw_event_id": Raw.search([("event_id", "=", oid)], limit=1).id})
    Item.create({"run_id": cod.id, "side": "bank", "item_ref": "DEMO-COD-BATCH-1", "amount": 99000.0,
                 "item_date": date(2026, 11, 9), "source_label": "DEMO bank BANK-001"})
    gw = Run.create({"name": "DEMO R04 gateway payout DEMO-PAYOUT-7 (DEMO Gateway)", "run_type": "gateway",
                     "period": "2026-11", "is_demo": True})
    for oid, ch, pay, prod, amt, d in orders:
        if pay == "PREPAID":
            Item.create({"run_id": gw.id, "side": "source", "item_ref": f"GWTX-{oid[-4:]}",
                         "batch_ref": "DEMO-PAYOUT-7", "amount": amt, "item_date": d,
                         "source_label": "DEMO Gateway"})
    Item.create({"run_id": gw.id, "side": "bank", "item_ref": "DEMO-PAYOUT-7", "amount": 20000.0,
                 "item_date": date(2026, 11, 8), "source_label": "DEMO bank BANK-002"})
    Item.create({"run_id": gw.id, "side": "bank", "item_ref": "", "amount": 3500.0,
                 "item_date": date(2026, 11, 8), "source_label": "DEMO bank BANK-003 (unidentified)"})
    stock = Run.create({"name": "DEMO R07 Distribution Partner stock Nov", "run_type": "partner_stock", "period": "2026-11",
                        "is_demo": True})
    St = env["pharma.partner.stock.line"]
    St.create({"run_id": stock.id, "sku": "DEMO-SKU-A", "lot": "DEMO-LOT-01", "location": "DEMO-PARTNER-WH1",
               "opening": 100, "inward_accepted": 50, "sold_or_issued": 80, "returned_to_pharma": 5,
               "expired_damaged_documented": 3, "reported": 62, "is_demo": True})
    line = St.create({"run_id": stock.id, "sku": "DEMO-SKU-B", "lot": "DEMO-LOT-07", "location": "DEMO-PARTNER-WH1",
                      "opening": 40, "sold_or_issued": 8, "reported": 30, "is_demo": True})
    fin = env.ref("base.user_admin")
    cod.with_user(fin).action_match()
    gw.with_user(fin).action_match()
    St.search([("run_id", "=", stock.id)]).action_raise_exceptions()
