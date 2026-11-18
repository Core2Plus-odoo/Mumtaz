"""Idempotent seeder for the Pharma DEMO tenant. Every record is fictional and
flagged DEMO. Natural keys (rule code, SKU, login, run name, event id, order
reference) decide whether a record already exists, so `seed()` can run on a
fresh install (post_init_hook) and again on every upgrade (post-migrate)
without creating anything twice. Real business methods are used wherever one
exists (approve, match, take ownership, propose / approve closure, confirm,
post), so the data went through the same code a user would exercise."""
import json
import logging
from datetime import date

from odoo import SUPERUSER_ID, api, models
from odoo.exceptions import UserError

from . import demo_images

_logger = logging.getLogger(__name__)

DEMO_USERS = {
    # role: (login, name, pharma groups, extra groups). Logins are "pharma.*" so they never collide with
    # the users the module test suites create in their own setUp ("demo_ops", "demo_maker", ...).
    "ops": ("pharma.ops", "DEMO Operations User", ["group_pharma_user"], []),
    "maker": ("pharma.maker", "DEMO Tax Maker (admin role)", ["group_pharma_admin"], ["product.group_product_manager"]),
    "approver": ("pharma.approver", "DEMO Tax Approver", ["group_pharma_tax_approver"], ["product.group_product_manager"]),
    "finance": ("pharma.finance", "DEMO Finance Controller", ["group_pharma_finance"], []),
}
DEMO_LOGINS = [v[0] for v in DEMO_USERS.values()]
# 19.0.1.1.0 seeded these logins; 19.0.1.1.1 renames them in place instead of creating a second set
LEGACY_LOGINS = {"ops": "demo_ops", "maker": "demo_maker", "approver": "demo_approver", "finance": "demo_finance"}

ORDERS = [  # order, channel, payment, sku, amount, date
    ("DEMO-O-1001", "shopify", "COD", "DEMO-SKU-A", 10000, date(2026, 11, 3)),
    ("DEMO-O-1002", "shopify", "COD", "DEMO-SKU-A", 45000, date(2026, 11, 3)),
    ("DEMO-O-1003", "odoo_website", "COD", "DEMO-SKU-B", 45000, date(2026, 11, 4)),
    ("DEMO-O-1004", "shopify", "PREPAID", "DEMO-SKU-A", 8000, date(2026, 11, 4)),
    ("DEMO-O-1005", "odoo_website", "PREPAID", "DEMO-SKU-B", 12000, date(2026, 11, 5)),
    ("DEMO-O-1006", "shopify", "COD", "DEMO-SKU-C", 6000, date(2026, 11, 5)),
]


class PharmaDemoSeed(models.AbstractModel):
    _name = "pharma.demo.seed"
    _description = "Pharma DEMO data seeder (fictional, idempotent)"

    # ------------------------------------------------------------------ entry
    @api.model
    def seed(self):
        env = api.Environment(self.env.cr, SUPERUSER_ID, {"no_reset_password": True, "mail_create_nolog": True,
                                                          "tracking_disable": True})
        s = env["pharma.demo.seed"]
        env["ir.config_parameter"].set_param("pharma.mode", "demo")
        if env.company.name != "Pharma Demo Co":
            env.company.write({"name": "Pharma Demo Co"})
        users = s._seed_users()
        s._seed_rules(users)
        prods = s._seed_products(users)
        s._refresh_images()
        s._seed_events(prods)
        s._seed_runs(users, prods)
        s._seed_partner_stock(users)
        s._seed_scenario_gate()
        s._seed_exception_states(users)
        s._seed_sales_and_invoices(prods)
        _logger.info("pharma_demo_data: seed complete (idempotent)")
        return True

    @api.model
    def set_demo_passwords(self, password):
        """Called from the staging script with an interactively typed password. Never stored in code."""
        users = self.env["res.users"].sudo().search([("login", "in", DEMO_LOGINS)])
        users.write({"password": password})
        return users.mapped("login")

    # ------------------------------------------------------------------ users
    def _seed_users(self):
        env = self.env
        Users = env["res.users"].with_context(no_reset_password=True)
        base = env.ref("base.group_user").id
        out = {"admin": env.ref("base.user_admin")}
        for role, (login, name, pgroups, extra) in DEMO_USERS.items():
            u = Users.search([("login", "=", login)], limit=1)
            if not u:
                legacy = Users.search([("login", "=", LEGACY_LOGINS[role]), ("name", "=", name)], limit=1)
                if legacy:
                    legacy.write({"login": login, "email": f"{login}@example.invalid"})
                    u = legacy
            if not u:
                gids = [base] + [env.ref(f"pharma_core.{g}").id for g in pgroups] + [env.ref(x).id for x in extra]
                u = Users.create({"name": name, "login": login, "email": f"{login}@example.invalid",
                                  "group_ids": [(6, 0, gids)]})
            out[role] = u
        # Demo convenience ONLY: admin may try every role. Maker-checker is shown with the demo users.
        admin_groups = [env.ref(f"pharma_core.{g}").id for g in
                        ("group_pharma_finance", "group_pharma_tax_approver", "group_pharma_admin")]
        out["admin"].write({"group_ids": [(4, g) for g in admin_groups]})
        return out

    # ------------------------------------------------------------------ rules
    def _rule(self, users, name, ttype, tclass, rate, dfrom, dto=None, state="approved", creator=None,
              legal="DEMO-LEGAL-REF", evid="DEMO-EVID-1"):
        Rule = self.env["pharma.tax.rule"]
        r = Rule.search([("name", "=", name)], limit=1)
        if r:
            return r
        vals = {"name": name, "tax_type": ttype, "tax_class": tclass, "rate": rate, "date_from": dfrom,
                "date_to": dto, "legal_ref": legal, "evidence_ref": evid, "is_demo": True}
        if state == "draft":
            return Rule.with_user(creator or users["maker"]).create(vals)
        r = Rule.with_context(pharma_internal=True).create(dict(
            vals, state="approved", approved_by=users["approver"].id, approved_on="2026-01-01 00:00:00"))
        if state == "superseded":
            r.with_context(pharma_internal=True).write({"state": "superseded"})
        return r

    def _seed_rules(self, users):
        # DEMO_CLASS_X: the classification the approved SKUs carry
        self._rule(users, "DEMO-RULE-1", "SALES_TAX_OUTPUT", "DEMO_CLASS_X", 10.0, date(2026, 1, 1))
        self._rule(users, "DEMO-RULE-2", "INCOME_TAX_153_2A", "DEMO_CLASS_X", 2.0, date(2026, 1, 1))
        # effective dating: the 2025 rate ended on 31 Dec 2025
        self._rule(users, "DEMO-RULE-0", "SALES_TAX_OUTPUT", "DEMO_CLASS_X", 8.0, date(2025, 1, 1), date(2025, 12, 31))
        # maker-checker: drafted by the maker, waiting for the approver (approver may approve live)
        self._rule(users, "DEMO-RULE-3", "SALES_TAX_WITHHOLDING", "DEMO_CLASS_X", 1.0, date(2026, 1, 1),
                   state="draft", legal="DEMO-LEGAL-REF-3", evid="DEMO-EVID-3")
        # evidence missing: approval must be refused
        self._rule(users, "DEMO-RULE-4", "PROVINCIAL_SERVICE_TAX", "DEMO_CLASS_X", 5.0, date(2026, 1, 1),
                   state="draft", legal="DEMO-LEGAL-REF-4", evid=False)
        # DEMO_CLASS_Y: two approved rules overlap -> ambiguous -> blocked
        self._rule(users, "DEMO-RULE-5", "SALES_TAX_OUTPUT", "DEMO_CLASS_Y", 10.0, date(2026, 1, 1))
        self._rule(users, "DEMO-RULE-6", "SALES_TAX_OUTPUT", "DEMO_CLASS_Y", 12.0, date(2026, 1, 1))
        # DEMO_CLASS_Z: a superseded rule, kept for history
        self._rule(users, "DEMO-RULE-7", "SALES_TAX_OUTPUT", "DEMO_CLASS_Z", 9.0, date(2025, 6, 1), state="superseded")

    # --------------------------------------------------------------- products
    def _product(self, users, code, name, price, tax_class=None, status="pending", proposer=None,
                 blurb="", scenario=""):
        """status: approved | pending | proposed (class + evidence set by the maker, not yet approved).
        `blurb` is the public shop copy (no health claims); `scenario` is the internal note that explains
        which control the product demonstrates."""
        Prod = self.env["product.template"]
        p = Prod.search([("default_code", "=", code)], limit=1)
        public = f"{blurb} Fictional product for the demo storefront. No health claims.".strip()
        notes = f"<p>DEMO scenario: {scenario}</p>" if scenario else False
        if not p:
            p = Prod.create({"name": name, "default_code": code, "type": "consu", "is_storable": True,
                             "list_price": price, "sale_ok": True, "description_sale": public, "description": notes})
            if status == "approved":
                p.with_context(pharma_internal=True).write({
                    "pharma_tax_class": tax_class, "pharma_tax_evidence_ref": "DEMO-EVID-1",
                    "pharma_tax_status": "approved", "pharma_tax_approved_by": users["approver"].id,
                    "pharma_tax_proposed_by": users["maker"].id})
            elif status == "proposed":
                p.with_user(proposer or users["maker"]).write({
                    "pharma_tax_class": tax_class, "pharma_tax_evidence_ref": "DEMO-EVID-5"})
        elif p.name.startswith("DEMO Wellness Product"):
            # 19.0.1.1.1: replace the engineering-style names from the first build with the shop-ready ones
            p.write({"name": name, "description_sale": public, "description": notes})
        return p.product_variant_id

    def _refresh_images(self):
        """Pack art is versioned: a DB seeded with an older style gets the current one exactly once."""
        P = self.env["ir.config_parameter"]
        done = P.get_param("pharma.demo.image_version") == demo_images.VERSION
        for p in self.env["product.template"].search([("default_code", "in", list(demo_images.STYLES))]):
            if done and p.image_1920:
                continue
            img = demo_images.b64(p.default_code)
            if img:
                p.write({"image_1920": img})
        P.set_param("pharma.demo.image_version", demo_images.VERSION)

    def _seed_products(self, users):
        P = {}
        P["A"] = self._product(
            users, "DEMO-SKU-A", "Green Leaf Infusion (DEMO)", 1000.0, "DEMO_CLASS_X", "approved",
            blurb="A light whole-leaf infusion with a fresh, grassy finish.",
            scenario="approved tax classification. Confirms and posts normally; resolves to the effective-dated rules.")
        P["B"] = self._product(
            users, "DEMO-SKU-B", "Golden Chai Blend (DEMO)", 1000.0, "DEMO_CLASS_X", "approved",
            blurb="Warming spices and black tea, ready to steep.",
            scenario="approved tax classification. Second SKU on the clean path (website channel COD order).")
        P["C"] = self._product(
            users, "DEMO-SKU-C", "Rose Petal Tea (DEMO)", 1000.0,
            blurb="Soft floral notes from dried rose petals.",
            scenario="NO approved tax classification. Sale order confirm and invoice post are blocked by the tax gate.")
        P["D"] = self._product(
            users, "DEMO-SKU-D", "Lavender Evening Infusion (DEMO)", 1500.0, "DEMO_CLASS_Y", "approved",
            blurb="Lavender and chamomile, caffeine free.",
            scenario="approved classification, but two approved rules overlap for DEMO_CLASS_Y: resolves as blocked / ambiguous.")
        P["E"] = self._product(
            users, "DEMO-SKU-E", "Warm Spice Mix (DEMO)", 800.0, "DEMO_CLASS_X", "proposed",
            blurb="Cinnamon, ginger and cardamom for baking and drinks.",
            scenario="classification PROPOSED by the maker, waiting for the Tax Approver (maker-checker).")
        return P

    # ----------------------------------------------------------------- events
    def _seed_events(self, prods):
        env = self.env
        Raw, Rule, Event = env["pharma.raw.event"], env["pharma.tax.rule"], env["pharma.tax.event"]
        by_code = {p.default_code: p for p in prods.values()}
        for oid, ch, pay, sku, amt, d in ORDERS:
            prod = by_code[sku]
            if not Raw.search_count([("source", "=", ch), ("event_id", "=", oid)]):
                Raw.ingest(ch, oid, json.dumps({"order": oid, "payment": pay, "sku": sku, "total": amt,
                                                "date": str(d), "DEMO": True}), is_demo=True)
            if Rule.resolve(prod, d, amt, "SALES_TAX_OUTPUT")["resolution"] == "resolved":
                for ttype in (["SALES_TAX_OUTPUT"] + (["INCOME_TAX_153_2A"] if pay == "COD" else [])):
                    if not Event.search_count([("order_ref", "=", oid), ("tax_type", "=", ttype), ("kind", "=", "original")]):
                        Event.post_event(oid, ch, f"DEMO-SET-{oid[-4:]}", ttype, prod, d, amt)
        # replay of the same payload is ignored (no second record)
        dup = json.dumps({"order": "DEMO-O-1007", "payment": "COD", "sku": "DEMO-SKU-B", "total": 3000,
                          "date": "2026-11-06", "DEMO": True})
        Raw.ingest("shopify", "DEMO-O-1007", dup, is_demo=True)
        Raw.ingest("shopify", "DEMO-O-1007", dup, is_demo=True)
        # same event id, different payload -> flagged conflict, never overwritten
        first = json.dumps({"order": "DEMO-O-1008", "payment": "PREPAID", "sku": "DEMO-SKU-A", "total": 9000,
                            "date": "2026-11-06", "DEMO": True})
        Raw.ingest("odoo_website", "DEMO-O-1008", first, is_demo=True)
        Raw.ingest("odoo_website", "DEMO-O-1008", first.replace("9000", "9500"), is_demo=True)
        # reversal: prepaid order DEMO-O-1004 was cancelled after posting
        orig = Event.search([("order_ref", "=", "DEMO-O-1004"), ("tax_type", "=", "SALES_TAX_OUTPUT"),
                             ("kind", "=", "original")], limit=1)
        if orig and not Event.search_count([("reversal_of", "=", orig.id)]):
            orig.action_reverse()

    # ------------------------------------------------------------------- runs
    def _run(self, users, name, vals, items, match=True):
        Run, Item = self.env["pharma.recon.run"], self.env["pharma.recon.item"]
        run = Run.search([("name", "=", name)], limit=1)
        if run:
            return run
        run = Run.create(dict(vals, name=name, is_demo=True))
        for it in items:
            Item.create(dict(it, run_id=run.id))
        if match:
            run.with_user(users["finance"]).action_match()
        return run

    def _seed_runs(self, users, prods):
        Raw = self.env["pharma.raw.event"]

        def raw(oid):
            return Raw.search([("event_id", "=", oid)], limit=1).id

        # R03 COD batch 1: variance -> exception, nothing adjusted (Blueprint example)
        cod = [dict(side="source", item_ref=f"AWB-{o[-4:]}", batch_ref="DEMO-COD-BATCH-1", amount=amt, item_date=d,
                    source_label="DEMO Courier A statement", raw_event_id=raw(o))
               for o, ch, pay, sku, amt, d in ORDERS if pay == "COD"]
        cod.append(dict(side="bank", item_ref="DEMO-COD-BATCH-1", amount=99000.0, item_date=date(2026, 11, 9),
                        source_label="DEMO bank BANK-001"))
        self._run(users, "DEMO R03 COD batch DEMO-COD-BATCH-1 (DEMO Courier A)",
                  dict(run_type="cod", period="2026-11", authorized_deductions=5000.0), cod)
        # R03 COD batch 2: clean one-to-many match, gross 50,000 less 2,500 fee = 47,500 received
        self._run(users, "DEMO R03 COD batch DEMO-COD-BATCH-2 (DEMO Courier A) — clean",
                  dict(run_type="cod", period="2026-11", authorized_deductions=2500.0), [
                      dict(side="source", item_ref="AWB-2001", batch_ref="DEMO-COD-BATCH-2", amount=30000.0,
                           item_date=date(2026, 11, 10), source_label="DEMO Courier A statement"),
                      dict(side="source", item_ref="AWB-2002", batch_ref="DEMO-COD-BATCH-2", amount=20000.0,
                           item_date=date(2026, 11, 10), source_label="DEMO Courier A statement"),
                      dict(side="bank", item_ref="DEMO-COD-BATCH-2", amount=47500.0, item_date=date(2026, 11, 14),
                           source_label="DEMO bank BANK-004")])
        # R04 gateway payout: short payout + an unidentified credit
        gw = [dict(side="source", item_ref=f"GWTX-{o[-4:]}", batch_ref="DEMO-PAYOUT-7", amount=amt, item_date=d,
                   source_label="DEMO Gateway") for o, ch, pay, sku, amt, d in ORDERS if pay == "PREPAID"]
        gw += [dict(side="bank", item_ref="DEMO-PAYOUT-7", amount=20000.0, item_date=date(2026, 11, 8),
                    source_label="DEMO bank BANK-002"),
               dict(side="bank", item_ref="", amount=3500.0, item_date=date(2026, 11, 8),
                    source_label="DEMO bank BANK-003 (unidentified)")]
        self._run(users, "DEMO R04 gateway payout DEMO-PAYOUT-7 (DEMO Gateway)",
                  dict(run_type="gateway", period="2026-11"), gw)
        # R05 bank vs ledger: exact ref, ref-with-amount-difference, ambiguous amount/date, low-confidence match
        self._run(users, "DEMO R05 Bank vs ledger Nov",
                  dict(run_type="bank", period="2026-11", date_window_days=3), [
                      dict(side="source", item_ref="LEDGER-001", amount=15000.0, item_date=date(2026, 11, 10), source_label="DEMO ledger"),
                      dict(side="bank", item_ref="LEDGER-001", amount=15000.0, item_date=date(2026, 11, 10), source_label="DEMO bank BANK-010"),
                      dict(side="source", item_ref="LEDGER-002", amount=7000.0, item_date=date(2026, 11, 11), source_label="DEMO ledger"),
                      dict(side="bank", item_ref="LEDGER-002", amount=7200.0, item_date=date(2026, 11, 11), source_label="DEMO bank BANK-011"),
                      dict(side="source", item_ref="LEDGER-003", amount=5000.0, item_date=date(2026, 11, 10), source_label="DEMO ledger"),
                      dict(side="source", item_ref="LEDGER-004", amount=5000.0, item_date=date(2026, 11, 11), source_label="DEMO ledger"),
                      dict(side="bank", item_ref="", amount=5000.0, item_date=date(2026, 11, 10), source_label="DEMO bank BANK-012 (no reference)"),
                      dict(side="source", item_ref="LEDGER-005", amount=2750.0, item_date=date(2026, 11, 12), source_label="DEMO ledger"),
                      dict(side="bank", item_ref="", amount=2750.0, item_date=date(2026, 11, 13), source_label="DEMO bank BANK-013 (no reference)")])

    # ---------------------------------------------------------- partner stock
    def _seed_partner_stock(self, users):
        St = self.env["pharma.partner.stock.line"]
        run = self._run(users, "DEMO R07 Distribution Partner stock Nov",
                        dict(run_type="partner_stock", period="2026-11"), [], match=False)
        lines = [
            dict(sku="DEMO-SKU-A", lot="DEMO-LOT-01", location="DEMO-PARTNER-WH1", opening=100, inward_accepted=50,
                 sold_or_issued=80, returned_to_pharma=5, expired_damaged_documented=3, reported=62),   # variance 0
            dict(sku="DEMO-SKU-B", lot="DEMO-LOT-07", location="DEMO-PARTNER-WH1", opening=40, sold_or_issued=8,
                 reported=30),                                                                         # variance -2
            dict(sku="DEMO-SKU-D", lot="DEMO-LOT-11", location="DEMO-PARTNER-WH2", opening=25, inward_accepted=10,
                 sold_or_issued=12, reported=23),                                                      # variance 0
            dict(sku="DEMO-SKU-A", lot="DEMO-LOT-02", location="DEMO-PARTNER-WH2", opening=60, sold_or_issued=20,
                 expired_damaged_documented=2, reported=41),                                           # variance +3
        ]
        for l in lines:
            if not St.search_count([("run_id", "=", run.id), ("sku", "=", l["sku"]), ("lot", "=", l["lot"])]):
                St.create(dict(l, run_id=run.id, is_demo=True))
        St.search([("run_id", "=", run.id)]).action_raise_exceptions()   # idempotent: one open exception per variance

    def _seed_scenario_gate(self):
        Sc = self.env["pharma.partner.scenario"]
        if not Sc.search_count([]):
            # chosen but not contracted / signed off -> custody recorded, revenue BLOCKED
            Sc.create({"name": "Distribution Partner commercial model", "scenario": "B", "contract_ref": False})

    # ------------------------------------------------------------- exceptions
    def _exc(self, run_name, needle):
        run = self.env["pharma.recon.run"].search([("name", "=", run_name)], limit=1)
        return self.env["pharma.recon.exception"].search(
            [("run_id", "=", run.id), ("description", "like", needle)], limit=1) if run else self.env["pharma.recon.exception"]

    def _seed_exception_states(self, users):
        fin, admin = users["finance"], users["admin"]
        # investigating: owner took it
        e = self._exc("DEMO R04 gateway payout DEMO-PAYOUT-7 (DEMO Gateway)", "Unidentified bank item")
        if e and e.state == "open":
            e.with_user(fin).action_assign_to_me()
        # pending approval: proposed by Finance, waits for ANOTHER Finance Controller (maker-checker)
        e = self._exc("DEMO R03 COD batch DEMO-COD-BATCH-1 (DEMO Courier A)", "variance")
        if e and e.state == "open":
            e.with_user(fin).action_assign_to_me()
            e.write({"resolution": "explained", "note": "DEMO: courier statement shows 2 parcels returned after cut-off; "
                                                        "awaiting credit note DEMO-CN-17 (fictional)."})
            e.with_user(fin).action_propose_close()
        # closed: proposed by Finance, approved by a different controller
        e = self._exc("DEMO R05 Bank vs ledger Nov", "amount differs")
        if e and e.state == "open":
            e.with_user(fin).action_assign_to_me()
            e.write({"resolution": "matched_manual", "note": "DEMO: bank credited 7,200 = ledger 7,000 + 200 "
                                                             "customer overpayment, refunded DEMO-REF-9 (fictional)."})
            e.with_user(fin).action_propose_close()
            e.with_user(admin).action_approve_close()

    # ----------------------------------------------------- sales and invoices
    def _seed_sales_and_invoices(self, prods):
        env = self.env
        partner = env["res.partner"].search([("name", "=", "DEMO Customer (fictional)")], limit=1) or \
            env["res.partner"].create({"name": "DEMO Customer (fictional)", "email": "demo.customer@example.invalid",
                                       "street": "DEMO street 1", "city": "DEMO City"})
        SO = env["sale.order"]

        def order(ref, product, qty, confirm):
            so = SO.search([("client_order_ref", "=", ref)], limit=1)
            if so:
                return so
            so = SO.create({"partner_id": partner.id, "client_order_ref": ref, "origin": "DEMO " + ref,
                            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": qty,
                                                   "price_unit": product.list_price})]})
            if confirm:
                so.action_confirm()
            return so

        # approved SKU: confirms normally
        order("DEMO-SO-OK", prods["A"], 2, confirm=True)
        # pending SKU: stays a quotation; "Confirm" is refused by the tax gate
        order("DEMO-SO-BLOCKED", prods["C"], 1, confirm=False)

        def sale_journal():
            return env["account.journal"].search_count([("type", "=", "sale"), ("company_id", "=", env.company.id)])
        if not sale_journal():
            # On a fresh -i run Odoo auto-installs the chart of accounts AFTER this hook; a demo company
            # without a country gets the generic chart anyway, so load it now rather than skip the invoices.
            try:
                env["account.chart.template"].try_loading("generic_coa", env.company, install_demo=False)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("pharma_demo_data: generic chart not loaded (%s)", exc)
        if not sale_journal():
            _logger.warning("pharma_demo_data: no sale journal, invoice scenarios skipped")
            return
        Move = env["account.move"]

        def invoice(ref, product, post):
            inv = Move.search([("ref", "=", ref), ("move_type", "=", "out_invoice")], limit=1)
            if inv:
                return inv
            inv = Move.create({"move_type": "out_invoice", "partner_id": partner.id, "ref": ref,
                               "invoice_date": date(2026, 11, 6),
                               "invoice_line_ids": [(0, 0, {"product_id": product.id, "quantity": 1,
                                                            "price_unit": product.list_price})]})
            if post:
                try:
                    inv.action_post()
                except UserError as exc:  # pragma: no cover - chart of accounts missing on an odd DB
                    _logger.warning("pharma_demo_data: could not post %s: %s", ref, exc)
            return inv

        invoice("DEMO-INV-OK", prods["A"], post=True)        # approved SKU: posts
        invoice("DEMO-INV-BLOCKED", prods["C"], post=False)  # pending SKU: stays draft, "Confirm" is refused
