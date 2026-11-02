#!/usr/bin/env python3
"""Provision a fresh Odoo demonstration database for the Enquiry-to-Cash
(trading / distribution) process — all eleven steps, end to end.

What it builds, in the order of the process chart:

    1  Customer Enquiry / RFQ          CRM lead, stages, deadline, estimator
    2  Technical Review & Sourcing     supplier price lists, RFQ to vendors
    3  Costing & Margin Control        product cost, landed cost, sale margin
    4  Internal Approval               margin/discount gate + approval activity
    5  Customer Quotation              quotation, validity, follow-up cadence
    6  Customer Decision               won / lost reasons / revision (requote)
    7  Customer PO & Sales Order       client PO reference, credit limit check
    8  Procurement / Stock Allocation  purchase requisition, vendor PO, receipt
    9  Delivery & POD                  picking, partial delivery, POD capture
   10  Invoicing & Collection          invoice, due dates, payment, follow-up
   11  Profitability & Mgmt Review     estimated vs actual margin, KPIs

Standard-first, in the house ladder: standard Odoo apps and configuration
first, then native automation (Automation Rules + Scheduled Actions) for the
approvals and the nine exception alerts, then Studio-equivalent `x_` fields
for the handful of states standard Odoo has no home for (POD, approval
stamps). No custom module is installed.

Everything is idempotent: each step is an `ensure` (create only when missing),
so the script can be re-run, resumed with `--only`, or pointed at an existing
database with `--no-create` without duplicating anything.

Usage, on the VPS:

    cd /opt/mumtaz/c2p-delivery-system
    # plan only, touches nothing:
    python3 scripts/provision_demo_db.py C2P_DEMO_E2C --dry-run

    # create and fill a brand new database:
    python3 scripts/provision_demo_db.py C2P_DEMO_E2C \
        --master-password "$ODOO_MASTER_PWD" --country AE

    # configure + seed a database that already exists:
    python3 scripts/provision_demo_db.py C2P_DEMO_E2C --no-create

    # re-run one phase after a fix:
    python3 scripts/provision_demo_db.py C2P_DEMO_E2C --no-create --only seed

Credentials: ODOO_URL / ODOO_USER / ODOO_PASSWORD from the environment or
delivery_api/.env, same precedence as scripts/inspect_odoo_db.py — what you
type on the command line wins over what is stored. The database master
password (for creating the database) comes from --master-password or
C2P_ODOO_MASTER_PWD; it is never written to disk or echoed back.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import xmlrpc.client
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "delivery_api"))

TODAY = date.today()


def load_env(path: Path) -> None:
    """Minimal .env loader — existing environment always wins."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def d(offset_days: int) -> str:
    """A date offset from today, as Odoo's wire format."""
    return (TODAY + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def dt(offset_days: int, hour: int = 9) -> str:
    """A datetime offset from today, as Odoo's wire format (UTC, naive)."""
    stamp = datetime.combine(TODAY + timedelta(days=offset_days),
                             datetime.min.time()).replace(hour=hour)
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


# ── modules ──────────────────────────────────────────────────────────────────
# Community-only. Every one of these ships with Odoo 19 CE; nothing here needs
# an Enterprise subscription, so the demo runs on the VPS as-is.
MODULES = [
    "contacts",            # customers and suppliers
    "crm",                 # step 1: enquiries / RFQ pipeline
    "sale_management",     # steps 5-7: quotations and sales orders
    "sale_margin",         # steps 3/11: cost and margin on every quote line
    "purchase",            # step 8: vendor RFQs and purchase orders
    "purchase_requisition",  # step 8: the purchase requisition in the chart
    "stock",               # steps 8-9: receipts, deliveries, allocation
    "sale_stock",          # links the sales order to its delivery
    "purchase_stock",      # links the purchase order to its receipt
    "stock_landed_costs",  # step 3: landed cost into the product cost
    "account",             # step 10: customer invoices and collection
    "base_automation",     # steps 4/9: approval and POD automation rules
    "account_payment",     # step 10: payment registration and reconciliation
]

# Odoo settings to switch on, as {res.config.settings field: value}. These are
# the standard toggles the eleven steps need — discounts per line (step 4),
# partner credit limits (step 7), multi-step delivery and lots (steps 8-9),
# units of measure and vendor price lists (steps 2-3).
SETTINGS = {
    "group_discount_per_so_line": True,     # step 4: discount control
    "group_uom": True,                      # step 2: units on technical specs
    "group_product_variant": False,
    "group_sale_delivery_address": True,    # step 9: ship-to vs bill-to
    "quotation_validity_days": 30,          # step 5: validity period
    "group_warning_sale": True,             # step 7: blocking warnings
    "group_auto_done_setting": False,
    "lock_confirmed_po": False,
    "group_stock_adv_location": False,
    "group_stock_multi_locations": True,    # step 8: stock allocation
    "group_stock_tracking_lot": True,       # step 9: packages on dispatch
    "group_analytic_accounting": True,      # step 11: profitability per deal
}


# ── plumbing ─────────────────────────────────────────────────────────────────
class Provisioner:
    """A thin, idempotent, dry-runnable wrapper over the Odoo XML-RPC bridge.

    `ensure` is the workhorse: search first, create only when missing, so the
    whole script is safe to re-run. Nothing writes in --dry-run; reads still
    happen, which is what makes the planned output accurate.
    """

    def __init__(self, db: str, url: str, user: str, password: str,
                 dry_run: bool = False):
        self.db, self.url = db, url.rstrip("/")
        self.user, self.password = user, password
        self.dry_run = dry_run
        self.log: list[str] = []
        self.created = 0
        self.reused = 0
        self.skipped: list[str] = []
        self._uid: Optional[int] = None
        self._models = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object", allow_none=True)
        self._common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common", allow_none=True)
        self._fake = -1          # id generator for dry-run placeholders
        self._field_cache: dict[str, set] = {}

    # -- connection -----------------------------------------------------------
    @property
    def uid(self) -> int:
        if self._uid is None:
            self._uid = self._common.authenticate(
                self.db, self.user, self.password, {})
            if not self._uid:
                raise PermissionError(
                    f"Odoo auth failed for db '{self.db}' as '{self.user}'")
        return self._uid

    # Odoo serialises XML-RPC responses with allow_none=False, so a method
    # that returns None (action_quotation_sent, action_set_lost,
    # action_apply_inventory) fails on the way back even though it ran and
    # committed server-side. Nothing the client sets can change that.
    NONE_RESULT = "cannot marshal None"

    def ex(self, model: str, method: str, *args, **kw) -> Any:
        try:
            return self._models.execute_kw(
                self.db, self.uid, self.password, model, method, list(args), kw)
        except Exception as exc:
            if self.NONE_RESULT in str(exc):
                return None      # the call succeeded; only its reply did not
            raise

    def say(self, line: str) -> None:
        self.log.append(line)
        print(line, flush=True)

    # -- introspection --------------------------------------------------------
    def has_model(self, model: str) -> bool:
        try:
            return bool(self.ex("ir.model", "search_count", [("model", "=", model)]))
        except Exception:
            return False

    def fields_of(self, model: str) -> set:
        """Field names of a model, cached. Used to drop values this Odoo build
        does not have rather than failing the whole phase on one renamed key."""
        if model not in self._field_cache:
            try:
                self._field_cache[model] = set(self.ex(model, "fields_get", [],
                                                       attributes=["type"]).keys())
            except Exception:
                self._field_cache[model] = set()
        return self._field_cache[model]

    def prune(self, model: str, values: dict) -> dict:
        """Keep only the values whose field exists on this model."""
        known = self.fields_of(model)
        if not known:
            return values
        dropped = [k for k in values if k not in known]
        if dropped:
            self.skipped.append(f"{model}: ignored unknown field(s) "
                                f"{', '.join(sorted(dropped))}")
        return {k: v for k, v in values.items() if k in known}

    # -- the idempotent primitives -------------------------------------------
    def find(self, model: str, domain: list) -> Optional[int]:
        try:
            ids = self.ex(model, "search", domain, limit=1)
        except Exception:
            return None
        return ids[0] if ids else None

    def ensure(self, model: str, domain: list, values: dict,
               label: str = "", update: bool = False) -> Optional[int]:
        """Create the record only when the domain finds nothing.

        `update=True` also writes the values onto an existing record, which is
        how configuration (stages, automations) stays correct after an edit,
        while demo transactions are left alone once created.
        """
        name = label or f"{model} {values.get('name', '')}".strip()
        existing = self.find(model, domain)
        if existing:
            self.reused += 1
            if update and not self.dry_run:
                try:
                    self.ex(model, "write", [existing], self.prune(model, values))
                except Exception as exc:
                    self.skipped.append(f"{name}: update failed — {brief(exc)}")
            self.say(f"   = {name} (exists, id={existing})")
            return existing
        if self.dry_run:
            self._fake -= 1
            self.say(f"   + {name} (would create)")
            return self._fake
        try:
            new_id = self.ex(model, "create", self.prune(model, values))
        except Exception as exc:
            self.skipped.append(f"{name}: create failed — {brief(exc)}")
            self.say(f"   ! {name} — {brief(exc)}")
            return None
        self.created += 1
        self.say(f"   + {name} (id={new_id})")
        return new_id

    def call(self, model: str, method: str, ids: list, label: str, **kw) -> Any:
        """Run a workflow method (confirm, validate, post) tolerantly: a demo
        that fails at step 9 should still report steps 1-8 as built."""
        if self.dry_run:
            self.say(f"   > {label} (would call {model}.{method})")
            return None
        try:
            result = self.ex(model, method, ids, **kw)
            self.say(f"   > {label}")
            return result
        except Exception as exc:
            self.skipped.append(f"{label}: {brief(exc)}")
            self.say(f"   ! {label} — {brief(exc)}")
            return None

    def write(self, model: str, ids: list, values: dict, label: str) -> None:
        if self.dry_run:
            self.say(f"   ~ {label} (would write)")
            return
        try:
            self.ex(model, "write", ids, self.prune(model, values))
            self.say(f"   ~ {label}")
        except Exception as exc:
            self.skipped.append(f"{label}: {brief(exc)}")
            self.say(f"   ! {label} — {brief(exc)}")


def brief(exc: Exception) -> str:
    """One readable line out of an XML-RPC fault's multi-line traceback."""
    text = str(exc)
    if isinstance(exc, xmlrpc.client.Fault):
        text = exc.faultString or text
    for line in reversed([l.strip() for l in text.splitlines() if l.strip()]):
        if not line.startswith(("File ", "Traceback", "  ")):
            return line[:300]
    return text.strip().replace("\n", " ")[:300]


# ── phase 1: the database itself ─────────────────────────────────────────────
def create_database(url: str, db: str, master_pwd: str, admin_pwd: str,
                    country: str, lang: str, demo: bool,
                    dry_run: bool) -> str:
    """Create the database through Odoo's `db` XML-RPC service.

    Passing a country code makes Odoo install that country's fiscal
    localization and chart of accounts, which step 10 needs — without it the
    invoices have nowhere to post.
    """
    proxy = xmlrpc.client.ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/db",
                                      allow_none=True)
    try:
        existing = list(proxy.list())
    except Exception as exc:
        existing = []
        print(f"note: could not list databases ({brief(exc)}); "
              f"continuing — creation will say if '{db}' is already there",
              file=sys.stderr)
    if db in existing:
        return f"database '{db}' already exists — configuring it in place"
    if dry_run:
        return f"would create database '{db}' (country={country}, lang={lang}, demo={demo})"
    if not master_pwd:
        raise SystemExit(
            "no database master password: pass --master-password or set "
            "C2P_ODOO_MASTER_PWD, or use --no-create against an existing database")
    proxy.create_database(master_pwd, db, demo, lang, admin_pwd, "admin",
                          country.upper(), False)
    return f"created database '{db}' (country={country}, lang={lang}, demo={demo})"


def install_modules(p: Provisioner, modules: list) -> None:
    """Install the apps the eleven steps need, in one immediate install."""
    try:
        recs = p.ex("ir.module.module", "search_read",
                    [("name", "in", modules)], fields=["name", "state"])
    except Exception as exc:
        p.skipped.append(f"module list unavailable: {brief(exc)}")
        p.say(f"   ! could not read the module list — {brief(exc)}")
        return
    by_name = {r["name"]: r for r in recs}
    missing = [m for m in modules if m not in by_name]
    if missing:
        p.skipped.append("modules not on this server: " + ", ".join(missing))
        p.say(f"   ! not available on this server: {', '.join(missing)}")
    todo = [r["id"] for r in recs if r["state"] not in ("installed", "to upgrade")]
    done = [r["name"] for r in recs if r["state"] == "installed"]
    if done:
        p.say(f"   = already installed: {', '.join(sorted(done))}")
    if not todo:
        return
    names = sorted(by_name[n]["name"] for n in by_name
                   if by_name[n]["id"] in todo)
    if p.dry_run:
        p.say(f"   + would install: {', '.join(names)}")
        return
    p.say(f"   + installing {', '.join(names)} — this takes a few minutes")
    try:
        p.ex("ir.module.module", "button_immediate_install", todo)
    except Exception as exc:
        p.skipped.append(f"module install: {brief(exc)}")
        p.say(f"   ! install failed — {brief(exc)}")
        return
    p._field_cache.clear()   # new modules bring new fields
    p.say("   > install finished")


# ── phase 2: standard configuration ──────────────────────────────────────────
def apply_settings(p: Provisioner) -> None:
    """Switch on the standard options the process needs, through the same
    res.config.settings transient the Settings screen uses."""
    wanted = p.prune("res.config.settings", dict(SETTINGS))
    if not wanted:
        p.say("   ! res.config.settings unavailable — skipping toggles")
        return
    if p.dry_run:
        for key, val in sorted(wanted.items()):
            p.say(f"   ~ setting {key} = {val} (would apply)")
        return
    try:
        sid = p.ex("res.config.settings", "create", wanted)
        p.ex("res.config.settings", "execute", [sid])
        p.say(f"   ~ applied {len(wanted)} settings: {', '.join(sorted(wanted))}")
    except Exception as exc:
        p.skipped.append(f"settings: {brief(exc)}")
        p.say(f"   ! settings — {brief(exc)}")


def configure_company(p: Provisioner, name: str, currency: str) -> int:
    """Name the demo company and put it on the right currency."""
    cid = p.find("res.company", []) or 1
    # stock_sms rides in as a dependency and puts an SMS confirmation wizard in
    # front of every delivery validation. It is a company field, not a settings
    # one, in 19. `validate_picking` answers the wizard too, belt and braces.
    vals = {"name": name, "stock_move_sms_validation": False}
    cur = p.find("res.currency", [("name", "=", currency)])
    if cur:
        p.call("res.currency", "write", [cur], f"activate currency {currency}",
               vals={"active": True})
        vals["currency_id"] = cur
    p.write("res.company", [cid], vals, f"company → {name} ({currency})")
    return cid


def enable_accounting(p: Provisioner, company_id: int) -> None:
    """Switch on Odoo's full accounting features and give the demo somewhere
    for money to move.

    In Community the Accounting *app* is `account` (installed as Invoicing);
    what is missing by default is the full-features group and a bank journal.
    Granting the group is what turns the cut-down Invoicing menu into the full
    Accounting one — chart of accounts, journal entries, reconciliation.
    """
    for xmlid in ("account.group_account_manager", "account.group_account_user",
                  "analytic.group_analytic_accounting"):
        try:
            gid = p.ex("ir.model.data", "check_object_reference",
                       xmlid.split(".")[0], xmlid.split(".")[1])[1]
        except Exception:
            p.skipped.append(f"accounting group {xmlid} not found")
            continue
        group_field = ("group_ids" if "group_ids" in p.fields_of("res.users")
                       else "groups_id")
        # The connected user is who will be demoing, so grant it there too.
        p.write("res.users", [p.uid], {group_field: [(4, gid)]},
                f"accounting rights · {xmlid.split('.')[1]} → admin")

    # A bank account on the company partner, and a journal pointing at it, so
    # payments land somewhere and reconciliation is demonstrable.
    try:
        company = p.ex("res.company", "read", [company_id], fields=["partner_id"])
        owner = company[0]["partner_id"][0] if company else None
    except Exception as exc:
        p.skipped.append(f"company partner lookup: {brief(exc)}")
        return
    if not owner:
        p.skipped.append("company has no partner; bank journal not created")
        return
    iban = "AE070331234567890123456"
    bank = p.ensure("res.partner.bank", [("acc_number", "=", iban)],
                    {"acc_number": iban, "partner_id": owner},
                    "company bank account")
    if bank:
        p.ensure("account.journal", [("type", "=", "bank"), ("code", "=", "DBNK")],
                 {"name": "Demo Bank — ADCB", "type": "bank", "code": "DBNK",
                  "bank_account_id": bank, "company_id": company_id},
                 "bank journal · Demo Bank")


# The eleven-step cast. Sales raise and chase, Estimation costs, the Manager
# approves margin — so the approval gate at step 4 has someone to route to.
USERS = [
    ("Layla Haddad", "layla.sales@demo.local", "sales",
     ["sales_team.group_sale_salesman_all_leads"]),
    ("Omar Siddiqui", "omar.estimation@demo.local", "estimation",
     ["sales_team.group_sale_salesman_all_leads", "purchase.group_purchase_user"]),
    ("Rania Farouk", "rania.manager@demo.local", "manager",
     ["sales_team.group_sale_manager", "purchase.group_purchase_manager",
      "account.group_account_manager", "stock.group_stock_manager"]),
    ("Tariq Nasser", "tariq.warehouse@demo.local", "warehouse",
     ["stock.group_stock_user"]),
    ("Hana Yusuf", "hana.finance@demo.local", "finance",
     ["account.group_account_manager", "account.group_account_user",
      "sales_team.group_sale_salesman"]),
]


def ensure_users(p: Provisioner, password: str) -> dict:
    """Create the four role users, each in the groups their step needs."""
    out: dict = {}
    for name, login, key, groups in USERS:
        gids = []
        for xmlid in groups:
            try:
                gid = p.ex("ir.model.data", "check_object_reference",
                           xmlid.split(".")[0], xmlid.split(".")[1])
                gids.append(gid[1])
            except Exception:
                p.skipped.append(f"group {xmlid} not found (app not installed?)")
        # Odoo 19 renamed this field; `prune` silently dropped the old name,
        # which left all five demo users with no groups.
        group_field = ("group_ids" if "group_ids" in p.fields_of("res.users")
                       else "groups_id")
        vals = {"name": name, "login": login, "password": password,
                "email": login, group_field: [(4, g) for g in gids]}
        out[key] = p.ensure("res.users", [("login", "=", login)], vals,
                            f"user · {name} ({key})")
    return out


# Trading stock for the demo: cost and sale price on every line, so the margin
# at steps 3 and 11 is a real number rather than a placeholder.
PRODUCTS = [
    # (key, name, type, cost, price, default_code)
    ("pump",    "Centrifugal Pump CP-200 (75 kW)", "consu", 4200.0, 5880.0, "CP-200"),
    ("valve",   "Gate Valve 6in DN150 ANSI 150",   "consu",  310.0,  465.0, "GV-150"),
    ("pipe",    "Pipe 316L Seamless 6in x 6m",     "consu",  180.0,  252.0, "SP-316L"),
    ("gauge",   "Pressure Gauge 0-16 bar",         "consu",   45.0,   72.0, "PG-016"),
    ("flange",  "Flange Set ANSI 150 (pair)",      "consu",   95.0,  142.0, "FL-150"),
    ("motor",   "Explosion-proof Motor 90 kW",     "consu", 5600.0, 7560.0, "EM-090"),
    ("commiss", "Installation & Commissioning",    "service", 1800.0, 3500.0, "SVC-IC"),
    ("freight", "Freight & Handling",              "service",  600.0,  850.0, "SVC-FR"),
    # Wider catalogue for the historical volume and the step 11 reporting.
    ("pump_sm", "Centrifugal Pump CP-080 (22 kW)", "consu", 1850.0, 2590.0, "CP-080"),
    ("bfvalve", "Butterfly Valve 8in Wafer",       "consu",  420.0,  630.0, "BV-200"),
    ("ctrlvlv", "Control Valve 4in Pneumatic",     "consu", 2450.0, 3430.0, "CV-100"),
    ("bearing", "Spherical Roller Bearing 22320",  "consu",  290.0,  435.0, "BR-320"),
    ("coupling", "Flexible Coupling F-140",        "consu",  365.0,  511.0, "CP-140"),
    ("sealkit", "Mechanical Seal Kit 65mm",        "consu",  480.0,  720.0, "MS-065"),
    ("strainer", "Y-Strainer 6in CS",              "consu",  215.0,  322.0, "YS-150"),
    ("expjoint", "Rubber Expansion Joint 6in",     "consu",  185.0,  277.0, "EJ-150"),
    ("actuator", "Electric Actuator 24V",          "consu",  940.0, 1316.0, "EA-024"),
    ("transmit", "Pressure Transmitter 4-20mA",    "consu",  310.0,  465.0, "PT-420"),
    ("switchgr", "LV Switchgear Panel 400A",       "consu", 3850.0, 5390.0, "SG-400"),
    ("cable",   "XLPE Cable 4C x 35mm (per m)",    "consu",   18.0,   27.0, "CB-435"),
    ("gasket",  "Spiral Wound Gasket 6in",         "consu",   32.0,   51.0, "GS-150"),
    ("bolts",   "Stud Bolt Set M20 (per set)",     "consu",   44.0,   70.0, "SB-M20"),
    ("calib",   "On-site Calibration Service",     "service", 450.0,  950.0, "SVC-CL"),
    ("mainten", "Annual Maintenance Contract",     "service", 4200.0, 7800.0, "SVC-AMC"),
    ("survey",  "Site Survey & Technical Study",   "service", 700.0, 1450.0, "SVC-SV"),
]

CUSTOMERS = [
    # (key, name, credit limit, payment term days, note)
    ("almazroui", "Al Mazroui Engineering LLC", 500000.0, 30),
    ("gulfpetro", "Gulf Petrochem Services FZE", 350000.0, 45),
    ("emsteel",   "Emirates Steel Trading Co.",  200000.0, 30),
    ("desert",    "Desert Rock Contracting LLC", 150000.0, 60),
    ("sharjah",   "Sharjah Water Authority",     750000.0, 90),
    # Wider customer base for the historical volume.
    ("adnoc",     "Al Dhafra Industrial Services",400000.0, 45),
    ("jebel",     "Jebel Ali Marine Works LLC",   180000.0, 30),
    ("oasis",     "Oasis Water Treatment Co.",    260000.0, 45),
    ("falcon",    "Falcon Facilities Management", 120000.0, 30),
    ("ajman",     "Ajman Cement Industries",      320000.0, 60),
    ("rakpower",  "RAK Power & Utilities",        600000.0, 90),
    ("marina",    "Marina Towers Facility Co.",    90000.0, 30),
    ("gulfsteel", "Gulf Steel Fabricators FZC",   210000.0, 45),
]

SUPPLIERS = [
    ("nordic",  "Nordic Pump Works AS"),
    ("shanghai", "Shanghai Valve Industrial Ltd"),
    ("deutsche", "Deutsche Fittings GmbH"),
    ("logistics", "Khaleej Freight & Logistics"),
    ("italvalve", "Italvalve Produzione SRL"),
    ("bearingco", "Nippon Bearing Trading Co."),
    ("emirates_cbl", "Emirates Cable Industries"),
    ("instrum",  "Precision Instruments Pte Ltd"),
]

# Which supplier quotes which product, at what price, valid until when — the
# "expired supplier prices" alert in the chart needs one that has lapsed.
SUPPLIER_PRICES = [
    ("nordic",   "pump",   3980.0, 30),
    ("nordic",   "motor",  5350.0, 30),
    ("shanghai", "valve",   295.0, 14),
    ("shanghai", "flange",   88.0, -5),     # lapsed on purpose: alert fodder
    ("deutsche", "pipe",    172.0, 60),
    ("deutsche", "gauge",    41.0, -12),    # lapsed on purpose
]


def ensure_master_data(p: Provisioner) -> dict:
    """Products, customers with credit limits, suppliers and their price
    lists — steps 2, 3 and 7 all read from here."""
    refs: dict = {"product": {}, "customer": {}, "supplier": {}}

    cat = p.ensure("product.category", [("name", "=", "Traded Goods")],
                   {"name": "Traded Goods"}, "product category · Traded Goods")
    for key, name, kind, cost, price, code in PRODUCTS:
        vals = {"name": name, "type": kind, "standard_price": cost,
                "list_price": price, "default_code": code,
                "purchase_ok": True, "sale_ok": True}
        if kind == "consu":
            vals["is_storable"] = True      # Odoo 18+ replaced type 'product'
            if cat:
                vals["categ_id"] = cat
        pid = p.ensure("product.template", [("default_code", "=", code)], vals,
                       f"product · {name}", update=True)
        refs["product"][key] = pid

    for key, name, limit, term_days in CUSTOMERS:
        term = p.find("account.payment.term",
                      [("name", "ilike", f"{term_days} Days")])
        vals = {"name": name, "is_company": True, "customer_rank": 1,
                "credit_limit": limit, "use_partner_credit_limit": True,
                "email": f"procurement@{key}.demo", "phone": "+971 4 000 0000"}
        if term:
            vals["property_payment_term_id"] = term
        refs["customer"][key] = p.ensure("res.partner", [("name", "=", name)],
                                         vals, f"customer · {name}", update=True)

    for key, name in SUPPLIERS:
        refs["supplier"][key] = p.ensure(
            "res.partner", [("name", "=", name)],
            {"name": name, "is_company": True, "supplier_rank": 1,
             "email": f"sales@{key}.demo"}, f"supplier · {name}", update=True)

    for sup_key, prod_key, price, valid_days in SUPPLIER_PRICES:
        sup, prod = refs["supplier"].get(sup_key), refs["product"].get(prod_key)
        if not sup or not prod or prod < 0:
            continue
        label = f"supplier price · {sup_key}/{prod_key} @ {price}"
        p.ensure("product.supplierinfo",
                 [("partner_id", "=", sup), ("product_tmpl_id", "=", prod)],
                 {"partner_id": sup, "product_tmpl_id": prod, "price": price,
                  "min_qty": 1, "delay": 21,
                  "date_start": d(-60), "date_end": d(valid_days)},
                 label, update=True)
    return refs


# ── the chart's status model ─────────────────────────────────────────────────
# Step 1-6 statuses live on the CRM pipeline, exactly as the "RFQ" column of
# the Key System Statuses box lists them.
CRM_STAGES = [
    ("New", 10, False),
    ("Assigned", 20, False),
    ("Under Review", 30, False),
    ("Estimation", 40, False),
    ("Quotation", 50, False),
    ("Won", 60, True),
]

LOST_REASONS = ["Price too high", "Lost to competitor", "Budget withdrawn",
                "Lead time too long", "No supplier availability",
                "Technical specification not met"]

ACTIVITY_TYPES = [
    ("Technical Review", 2, "Review the technical specification and confirm "
                            "the items can be sourced."),
    ("Supplier Quotation Chase", 3, "Chase the supplier for a firm price and "
                                    "lead time."),
    ("Margin Approval", 1, "Approve or reject the price and margin on this "
                           "quotation."),
    ("Quotation Follow-up", 5, "Follow the customer up on the submitted "
                               "quotation."),
    ("POD Collection", 2, "Collect the signed proof of delivery."),
    ("Collection Call", 3, "Call the customer about the outstanding invoice."),
]


def ensure_pipeline(p: Provisioner, users: dict) -> dict:
    """The enquiry pipeline (step 1), its lost reasons (step 6) and the
    activity types the alerts and approvals schedule against."""
    refs: dict = {"stage": {}, "lost": {}, "activity": {}}

    team = p.ensure("crm.team", [("name", "=", "Trading Sales")],
                    {"name": "Trading Sales", "user_id": users.get("manager")},
                    "sales team · Trading Sales", update=True)
    refs["team"] = team

    for name, seq, is_won in CRM_STAGES:
        vals = {"name": name, "sequence": seq, "is_won": is_won}
        refs["stage"][name] = p.ensure(
            "crm.stage", [("name", "=", name)], vals,
            f"enquiry stage · {name}", update=True)

    for name in LOST_REASONS:
        refs["lost"][name] = p.ensure("crm.lost.reason", [("name", "=", name)],
                                      {"name": name}, f"lost reason · {name}")

    for name, delay, note in ACTIVITY_TYPES:
        refs["activity"][name] = p.ensure(
            "mail.activity.type", [("name", "=", name)],
            {"name": name, "delay_count": delay, "delay_unit": "days",
             "summary": name, "default_note": note},
            f"activity type · {name}", update=True)

    for name in ("Enquiry / RFQ", "Tender", "Repeat Customer", "Walk-in"):
        p.ensure("utm.source", [("name", "=", name)], {"name": name},
                 f"enquiry source · {name}")
    return refs


# ── phase 3: Studio-equivalent fields ────────────────────────────────────────
# Rung three of the ladder. Standard Odoo carries most of the chart's statuses
# already (sale.order.state, picking.state, move.payment_state), so these are
# only the states it has no home for: the approval stamp at step 4, the POD at
# step 9, and the sub-statuses the chart names that standard has no field for.
MANUAL_FIELDS = [
    # (model, name, label, ttype, extra)
    ("crm.lead", "x_required_by", "Required By", "date", {}),
    ("crm.lead", "x_estimator_id", "Estimator", "many2one",
     {"relation": "res.users"}),
    ("sale.order", "x_quote_status", "Quotation Status", "selection",
     {"selection": [("draft", "Draft"), ("pending_approval", "Pending Approval"),
                    ("approved", "Approved"), ("submitted", "Submitted"),
                    ("followup", "Follow-up"), ("won", "Won"), ("lost", "Lost"),
                    ("expired", "Expired")]}),
    ("sale.order", "x_margin_approved", "Margin Approved", "boolean", {}),
    ("sale.order", "x_margin_approved_by", "Approved By", "many2one",
     {"relation": "res.users"}),
    ("sale.order", "x_margin_approved_on", "Approved On", "datetime", {}),
    ("sale.order", "x_cost_sheet_ref", "Cost Sheet Ref", "char", {}),
    ("sale.order", "x_revision_of", "Revision Of", "many2one",
     {"relation": "sale.order"}),
    ("purchase.order", "x_po_status", "PO Status", "selection",
     {"selection": [("draft", "Draft"), ("pending_approval", "Pending Approval"),
                    ("approved", "Approved"), ("po_issued", "PO Issued"),
                    ("supplier_confirmed", "Supplier Confirmed"),
                    ("received", "Received"), ("direct_ship", "Direct Ship")]}),
    ("purchase.order", "x_direct_ship", "Direct Ship to Customer", "boolean", {}),
    ("stock.picking", "x_delivery_status", "Delivery Status", "selection",
     {"selection": [("planned", "Planned"), ("dispatched", "Dispatched"),
                    ("partial", "Partially Delivered"),
                    ("delivered", "Delivered"), ("pod_pending", "POD Pending"),
                    ("pod_received", "POD Received")]}),
    ("stock.picking", "x_pod_received", "POD Received", "boolean", {}),
    ("stock.picking", "x_pod_date", "POD Date", "date", {}),
    ("stock.picking", "x_pod_signed_by", "POD Signed By", "char", {}),
    ("account.move", "x_collection_status", "Collection Status", "selection",
     {"selection": [("due", "Due"), ("overdue", "Overdue"),
                    ("promised", "Payment Promised"), ("disputed", "Disputed"),
                    ("reconciled", "Paid & Reconciled")]}),
]


def model_id(p: Provisioner, model: str) -> Optional[int]:
    return p.find("ir.model", [("model", "=", model)])


def ensure_manual_fields(p: Provisioner) -> None:
    """Create the `x_` fields. `state='manual'` is what makes them Studio-style
    database fields rather than something a module owns."""
    for model, name, label, ttype, extra in MANUAL_FIELDS:
        mid = model_id(p, model)
        if not mid:
            p.skipped.append(f"{model}: model absent, skipped field {name}")
            continue
        vals = {"name": name, "model_id": mid, "model": model,
                "field_description": label, "ttype": ttype, "state": "manual",
                "store": True}
        if extra.get("relation"):
            vals["relation"] = extra["relation"]
        if ttype == "selection":
            vals["selection_ids"] = [
                (0, 0, {"value": v, "name": lbl, "sequence": (i + 1) * 10})
                for i, (v, lbl) in enumerate(extra["selection"])]
        p.ensure("ir.model.fields",
                 [("model", "=", model), ("name", "=", name)], vals,
                 f"field · {model}.{name} ({label})")
    p._field_cache.clear()


# ── phase 4: native automation ───────────────────────────────────────────────
MARGIN_FLOOR = 15.0      # % — below this a quotation needs step 4 approval
DISCOUNT_LIMIT = 10.0    # % — a bigger line discount needs step 4 approval

# Automation rules, as (name, model, trigger, filter_domain, trigger_fields, code).
AUTOMATIONS = [
    (
        "E2C · Step 4 — margin & discount approval gate",
        "sale.order", "on_create_or_write",
        "[('state', 'in', ['draft', 'sent'])]",
        ["amount_untaxed", "order_line"],
        """
# Route a quotation for approval when the margin is thin or a discount is deep.
floor = %(floor)s
disc_limit = %(disc)s
for order in records:
    if order.x_margin_approved:
        continue
    base = order.amount_untaxed or 0.0
    margin = order.margin or 0.0
    pct = (margin / base * 100.0) if base else 0.0
    deep = any((l.discount or 0.0) > disc_limit for l in order.order_line)
    if base and (pct < floor or deep):
        if order.x_quote_status != 'pending_approval':
            order.write({'x_quote_status': 'pending_approval'})
            reason = 'margin %%.1f%%%% below the %%s%%%% floor' %% (pct, floor)
            if deep:
                reason = reason + ' / line discount over %%s%%%%' %% disc_limit
            order.message_post(body='Held for approval: ' + reason)
            approver = order.user_id or order.create_uid
            open_acts = order.activity_ids.filtered(
                lambda a: a.summary == 'Margin Approval')
            if not open_acts:
                order.activity_schedule(
                    summary='Margin Approval', user_id=approver.id,
                    note='Approve the price and margin, or send back for re-costing.')
    elif order.x_quote_status in (False, 'pending_approval'):
        order.write({'x_quote_status': 'draft'})
""" % {"floor": MARGIN_FLOOR, "disc": DISCOUNT_LIMIT},
    ),
    (
        "E2C · Step 4 — stamp the approval",
        "sale.order", "on_create_or_write",
        "[('x_margin_approved', '=', True)]",
        ["x_margin_approved"],
        """
for order in records:
    vals = {}
    if order.x_quote_status in (False, 'draft', 'pending_approval'):
        vals['x_quote_status'] = 'approved'
    if not order.x_margin_approved_by:
        vals['x_margin_approved_by'] = env.user.id
    if not order.x_margin_approved_on:
        vals['x_margin_approved_on'] = datetime.datetime.now()
    if vals:
        order.write(vals)
    order.activity_ids.filtered(
        lambda a: a.summary == 'Margin Approval').action_feedback(
            feedback='Approved by ' + env.user.name)
""",
    ),
    (
        "E2C · Step 5 — quotation submitted, start the follow-up cadence",
        "sale.order", "on_create_or_write",
        "[('state', '=', 'sent')]", ["state"],
        """
for order in records:
    if order.x_quote_status not in ('submitted', 'followup', 'won', 'lost'):
        order.write({'x_quote_status': 'submitted'})
    if not order.activity_ids.filtered(lambda a: a.summary == 'Quotation Follow-up'):
        order.activity_schedule(
            summary='Quotation Follow-up',
            user_id=(order.user_id or order.create_uid).id,
            date_deadline=datetime.date.today() + datetime.timedelta(days=5),
            note='Call the customer about the submitted quotation.')
""",
    ),
    (
        "E2C · Step 6/7 — order won on confirmation",
        "sale.order", "on_create_or_write",
        "[('state', 'in', ['sale', 'done'])]", ["state"],
        """
for order in records:
    if order.x_quote_status != 'won':
        order.write({'x_quote_status': 'won'})
    if not order.client_order_ref:
        order.message_post(
            body='Customer PO reference is missing — verify the PO before execution (step 7).')
""",
    ),
    (
        "E2C · Step 8 — purchase order issued",
        "purchase.order", "on_create_or_write",
        "[('state', 'in', ['purchase', 'done'])]", ["state"],
        """
for po in records:
    if po.x_po_status in (False, 'draft', 'pending_approval', 'approved'):
        po.write({'x_po_status':
                  'direct_ship' if po.x_direct_ship else 'po_issued'})
""",
    ),
    (
        "E2C · Step 9 — delivery done, POD pending",
        "stock.picking", "on_create_or_write",
        "[('state', '=', 'done'), ('picking_type_code', '=', 'outgoing')]",
        ["state"],
        """
for pick in records:
    if pick.x_pod_received:
        continue
    if pick.x_delivery_status != 'pod_pending':
        pick.write({'x_delivery_status': 'pod_pending'})
    if not pick.activity_ids.filtered(lambda a: a.summary == 'POD Collection'):
        pick.activity_schedule(
            summary='POD Collection', user_id=env.uid,
            date_deadline=datetime.date.today() + datetime.timedelta(days=2),
            note='Collect and attach the signed proof of delivery.')
""",
    ),
    (
        "E2C · Step 9 — POD received",
        "stock.picking", "on_create_or_write",
        "[('x_pod_received', '=', True)]", ["x_pod_received"],
        """
for pick in records:
    vals = {}
    if pick.x_delivery_status != 'pod_received':
        vals['x_delivery_status'] = 'pod_received'
    if not pick.x_pod_date:
        vals['x_pod_date'] = datetime.date.today()
    if vals:
        pick.write(vals)
    pick.activity_ids.filtered(
        lambda a: a.summary == 'POD Collection').action_feedback(feedback='POD received')
""",
    ),
    (
        "E2C · Step 1 — assign the enquiry",
        "crm.lead", "on_create_or_write",
        "[('user_id', '!=', False), ('type', '=', 'opportunity')]", ["user_id"],
        """
assigned = env['crm.stage'].search([('name', '=', 'Assigned')], limit=1)
for lead in records:
    if assigned and lead.stage_id and lead.stage_id.name == 'New':
        lead.write({'stage_id': assigned.id})
""",
    ),
]


def ensure_automations(p: Provisioner) -> None:
    """Create the Automation Rules — rung two of the ladder, no code module."""
    if not p.has_model("base.automation"):
        p.say("   ! base_automation not installed — skipping automation rules")
        p.skipped.append("base.automation missing: approval + POD rules not created")
        return
    for name, model, trigger, domain, trig_fields, code in AUTOMATIONS:
        mid = model_id(p, model)
        if not mid:
            p.skipped.append(f"{name}: model {model} absent")
            continue
        field_ids = []
        for fname in trig_fields:
            fid = p.find("ir.model.fields",
                         [("model", "=", model), ("name", "=", fname)])
            if fid:
                field_ids.append(fid)
        vals = {
            "name": name, "model_id": mid, "trigger": trigger,
            "filter_domain": domain, "active": True,
            "trigger_field_ids": [(6, 0, field_ids)] if field_ids else False,
            "action_server_ids": [(0, 0, {
                "name": name, "model_id": mid, "state": "code",
                "code": code.strip(),
            })],
        }
        p.ensure("base.automation", [("name", "=", name)], vals,
                 f"automation · {name}")


# ── the nine alerts from the chart, as Scheduled Actions ─────────────────────
# (name, model, interval_number, interval_type, code)
ALERTS = [
    (
        "E2C Alert · Unassigned or overdue RFQs", "crm.lead", 1, "days",
        """
today = datetime.date.today()
leads = env['crm.lead'].search([('type', '=', 'opportunity'),
                                ('stage_id.is_won', '=', False)])
for lead in leads:
    late = lead.x_required_by and lead.x_required_by < today
    if not lead.user_id or late:
        why = 'Unassigned enquiry' if not lead.user_id else 'Enquiry past its required-by date'
        if not lead.activity_ids.filtered(lambda a: a.summary == why):
            lead.activity_schedule(summary=why, user_id=lead.team_id.user_id.id or env.uid,
                                   note=why + ' — assign an owner and progress it.')
""",
    ),
    (
        "E2C Alert · Expired supplier prices", "product.supplierinfo", 7, "days",
        """
today = datetime.date.today()
stale = env['product.supplierinfo'].search([('date_end', '!=', False),
                                            ('date_end', '<', today)])
if stale:
    names = ', '.join(s.product_tmpl_id.display_name for s in stale[:20])
    log('Expired supplier prices (%s): %s' % (len(stale), names), level='warning')
""",
    ),
    (
        "E2C Alert · Pending approvals ageing", "sale.order", 1, "days",
        """
cutoff = datetime.datetime.now() - datetime.timedelta(days=2)
held = env['sale.order'].search([('x_quote_status', '=', 'pending_approval'),
                                 ('write_date', '<', cutoff)])
for order in held:
    order.message_post(body='Still awaiting margin approval after 2 days (step 4).')
""",
    ),
    (
        "E2C Alert · Overdue quotation follow-ups", "sale.order", 1, "days",
        """
cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
quotes = env['sale.order'].search([('state', '=', 'sent'),
                                   ('date_order', '<', cutoff)])
for order in quotes:
    if order.x_quote_status != 'followup':
        order.write({'x_quote_status': 'followup'})
    if not order.activity_ids.filtered(lambda a: a.summary == 'Quotation Follow-up'):
        order.activity_schedule(summary='Quotation Follow-up',
                                user_id=(order.user_id or order.create_uid).id,
                                note='No customer decision after 7 days.')
""",
    ),
    (
        "E2C Alert · Customer credit limit breaches", "res.partner", 1, "days",
        """
partners = env['res.partner'].search([('credit_limit', '>', 0)])
for partner in partners:
    if (partner.credit or 0.0) > partner.credit_limit:
        log('Credit limit breached: %s owes %.2f against a limit of %.2f'
            % (partner.display_name, partner.credit, partner.credit_limit),
            level='warning')
""",
    ),
    (
        "E2C Alert · Delayed deliveries and missing POD", "stock.picking", 1, "days",
        """
today = datetime.date.today()
late = env['stock.picking'].search([('picking_type_code', '=', 'outgoing'),
                                    ('state', 'not in', ['done', 'cancel'])])
for pick in late:
    if pick.scheduled_date and pick.scheduled_date.date() < today:
        pick.message_post(body='Delivery is past its scheduled date (step 9).')
cutoff = datetime.datetime.now() - datetime.timedelta(days=3)
no_pod = env['stock.picking'].search([('state', '=', 'done'),
                                      ('picking_type_code', '=', 'outgoing'),
                                      ('x_pod_received', '=', False),
                                      ('date_done', '<', cutoff)])
for pick in no_pod:
    pick.message_post(body='Proof of delivery still outstanding after 3 days.')
""",
    ),
    (
        "E2C Alert · Overdue invoices", "account.move", 1, "days",
        """
today = datetime.date.today()
invoices = env['account.move'].search([('move_type', '=', 'out_invoice'),
                                       ('state', '=', 'posted'),
                                       ('payment_state', 'in', ['not_paid', 'partial'])])
for inv in invoices:
    overdue = inv.invoice_date_due and inv.invoice_date_due < today
    status = 'overdue' if overdue else 'due'
    if inv.x_collection_status != status:
        inv.write({'x_collection_status': status})
    if overdue and not inv.activity_ids.filtered(lambda a: a.summary == 'Collection Call'):
        inv.activity_schedule(summary='Collection Call',
                              user_id=(inv.invoice_user_id or env.user).id,
                              note='Invoice is past its due date — chase the payment.')
paid = env['account.move'].search([('move_type', '=', 'out_invoice'),
                                   ('state', '=', 'posted'),
                                   ('payment_state', 'in', ['paid', 'in_payment', 'reversed'])])
for inv in paid:
    if inv.x_collection_status != 'reconciled':
        inv.write({'x_collection_status': 'reconciled'})
""",
    ),
    (
        "E2C Alert · Cash forecast shortfall", "account.move", 7, "days",
        """
today = datetime.date.today()
horizon = today + datetime.timedelta(days=30)
inflow = 0.0
for inv in env['account.move'].search([('move_type', '=', 'out_invoice'),
                                       ('state', '=', 'posted'),
                                       ('payment_state', 'in', ['not_paid', 'partial']),
                                       ('invoice_date_due', '<=', horizon)]):
    inflow += inv.amount_residual
outflow = 0.0
for bill in env['account.move'].search([('move_type', '=', 'in_invoice'),
                                        ('state', '=', 'posted'),
                                        ('payment_state', 'in', ['not_paid', 'partial']),
                                        ('invoice_date_due', '<=', horizon)]):
    outflow += bill.amount_residual
if outflow > inflow:
    log('Cash forecast shortfall over 30 days: receivables %.2f vs payables %.2f'
        % (inflow, outflow), level='warning')
""",
    ),
    (
        "E2C Housekeeping · Expire lapsed quotations", "sale.order", 1, "days",
        """
today = datetime.date.today()
lapsed = env['sale.order'].search([('state', 'in', ['draft', 'sent']),
                                   ('validity_date', '!=', False),
                                   ('validity_date', '<', today)])
for order in lapsed:
    if order.x_quote_status != 'expired':
        order.write({'x_quote_status': 'expired'})
        order.message_post(body='Quotation validity has lapsed (step 5).')
""",
    ),
]


def cron_user(p: Provisioner) -> Optional[int]:
    """Owner for the scheduled actions — the connected user when we have one."""
    try:
        return p.uid
    except Exception:
        return None


def ensure_alerts(p: Provisioner) -> None:
    """The Automated Alerts & Exceptions panel of the chart, as ir.cron."""
    for name, model, every, unit, code in ALERTS:
        mid = model_id(p, model)
        if not mid:
            p.skipped.append(f"{name}: model {model} absent")
            continue
        vals = {"name": name, "model_id": mid, "state": "code",
                "code": code.strip(), "interval_number": every,
                "interval_type": unit, "active": True,
                "nextcall": dt(1, 6), "user_id": cron_user(p)}
        p.ensure("ir.cron", [("name", "=", name)], vals, f"alert · {name}")


# ── phase 5: demo transactions ───────────────────────────────────────────────
def product_variant(p: Provisioner, tmpl_id: int) -> Optional[int]:
    """The sellable product.product behind a product.template."""
    if not tmpl_id or tmpl_id < 0:
        return None
    try:
        rec = p.ex("product.product", "search_read",
                   [("product_tmpl_id", "=", tmpl_id)], fields=["id"], limit=1)
    except Exception as exc:
        p.skipped.append(f"product variant for template {tmpl_id}: {brief(exc)}")
        return None
    return rec[0]["id"] if rec else None


def stock_in(p: Provisioner, refs: dict, qty: float = 500.0) -> None:
    """Put stock on hand so step 9 can actually dispatch. An inventory
    adjustment is the standard way in; without it the pickings sit unreserved."""
    if p.dry_run:
        p.say(f"   ~ would stock {qty} of each storable product")
        return
    wh = p.ex("stock.warehouse", "search_read", [], fields=["lot_stock_id"], limit=1)
    if not wh:
        p.skipped.append("no warehouse found — stock not seeded")
        return
    location = wh[0]["lot_stock_id"][0]
    seeded = 0
    for key, tmpl in refs["product"].items():
        variant = product_variant(p, tmpl)
        if not variant:
            continue
        kind = p.ex("product.product", "read", [variant], fields=["type"])
        if kind and kind[0].get("type") == "service":
            continue
        try:
            existing = p.ex("stock.quant", "search",
                            [("product_id", "=", variant),
                             ("location_id", "=", location)], limit=1)
            if existing:
                on_hand = p.ex("stock.quant", "read", existing, fields=["quantity"])
                if on_hand and on_hand[0]["quantity"] >= qty:
                    continue
                p.ex("stock.quant", "write", existing, {"inventory_quantity": qty})
                p.ex("stock.quant", "action_apply_inventory", existing)
            else:
                qid = p.ex("stock.quant", "create",
                           {"product_id": variant, "location_id": location,
                            "inventory_quantity": qty})
                p.ex("stock.quant", "action_apply_inventory", [qid])
            seeded += 1
        except Exception as exc:
            p.skipped.append(f"stock for {key}: {brief(exc)}")
    p.say(f"   ~ stocked {seeded} products at {qty} units")


def validate_picking(p: Provisioner, picking_id: int, label: str,
                     ratio: float = 1.0) -> None:
    """Validate a picking, optionally delivering only part of it.

    A partial validation leaves a backorder, which is exactly the chart's
    "Partial delivery (if any)" branch, so the demo shows it for real.
    """
    if p.dry_run or not picking_id or picking_id < 0:
        p.say(f"   > {label} (would validate, ratio={ratio})")
        return
    try:
        state = p.ex("stock.picking", "read", [picking_id], fields=["state"])
        if state and state[0]["state"] in ("done", "cancel"):
            p.say(f"   = {label} (already {state[0]['state']})")
            return
        moves = p.ex("stock.move", "search_read",
                     [("picking_id", "=", picking_id)],
                     fields=["product_uom_qty"])
        for move in moves:
            p.ex("stock.move", "write", [move["id"]],
                 {"quantity": round(move["product_uom_qty"] * ratio, 2),
                  "picked": True})
        result = p.ex("stock.picking", "button_validate", [picking_id])
        # Validation can return a wizard, and answering that wizard can return
        # another (SMS confirmation, then the backorder question). Each wizard
        # has its own confirm method — `process` is not universal.
        methods = {
            "stock.backorder.confirmation": "process",
            "stock.immediate.transfer": "process",
            "confirm.stock.sms": "dont_send_sms",
        }
        for _ in range(4):
            if not (isinstance(result, dict) and result.get("res_model")):
                break
            wiz = result["res_model"]
            method = methods.get(wiz)
            if not method:
                p.skipped.append(f"{label}: unhandled wizard {wiz}")
                p.say(f"   ! {label} — unhandled wizard {wiz}")
                return
            ctx = result.get("context") or {}
            wid = p.ex(wiz, "create", {}, context=ctx)
            result = p.ex(wiz, method, [wid], context=ctx)
        p.say(f"   > {label}")
    except Exception as exc:
        p.skipped.append(f"{label}: {brief(exc)}")
        p.say(f"   ! {label} — {brief(exc)}")


def invoice_order(p: Provisioner, order_id: int, label: str,
                  inv_date_offset: int, due_offset: int) -> Optional[int]:
    """Raise and post the customer invoice for a sales order (step 10)."""
    if p.dry_run or not order_id or order_id < 0:
        p.say(f"   > {label} (would invoice)")
        return None
    try:
        existing = p.ex("sale.order", "read", [order_id], fields=["invoice_ids"])
        if existing and existing[0]["invoice_ids"]:
            inv_id = existing[0]["invoice_ids"][0]
            p.say(f"   = {label} (already invoiced, id={inv_id})")
            return inv_id
        ctx = {"active_model": "sale.order", "active_ids": [order_id],
               "active_id": order_id}
        wid = p.ex("sale.advance.payment.inv", "create",
                   {"advance_payment_method": "delivered"}, context=ctx)
        p.ex("sale.advance.payment.inv", "create_invoices", [wid], context=ctx)
        refreshed = p.ex("sale.order", "read", [order_id], fields=["invoice_ids"])
        inv_ids = refreshed[0]["invoice_ids"] if refreshed else []
        if not inv_ids:
            p.skipped.append(f"{label}: no invoice produced")
            p.say(f"   ! {label} — the wizard produced no invoice "
                  f"(nothing delivered to invoice yet?)")
            return None
        inv_id = inv_ids[0]
        p.ex("account.move", "write", [inv_id],
             {"invoice_date": d(inv_date_offset),
              "invoice_date_due": d(due_offset)})
        p.ex("account.move", "action_post", [inv_id])
        p.say(f"   > {label} (invoice id={inv_id})")
        return inv_id
    except Exception as exc:
        p.skipped.append(f"{label}: {brief(exc)}")
        p.say(f"   ! {label} — {brief(exc)}")
        return None


def pay_invoice(p: Provisioner, invoice_id: Optional[int], label: str,
                amount: Optional[float] = None, date_offset: int = 0) -> None:
    """Register a full or partial payment (step 10, 'Partially Paid' / 'Paid &
    Reconciled' in the chart's invoice statuses)."""
    if p.dry_run or not invoice_id:
        p.say(f"   > {label} (would pay)")
        return
    try:
        state = p.ex("account.move", "read", [invoice_id],
                     fields=["payment_state", "amount_residual"])
        if state and state[0]["payment_state"] in ("paid", "in_payment"):
            p.say(f"   = {label} (already settled)")
            return
        ctx = {"active_model": "account.move", "active_ids": [invoice_id],
               "active_id": invoice_id}
        vals: dict = {"payment_date": d(date_offset)}
        if amount is not None:
            vals["amount"] = amount
            vals["payment_difference_handling"] = "open"
        wid = p.ex("account.payment.register", "create", vals, context=ctx)
        p.ex("account.payment.register", "action_create_payments", [wid], context=ctx)
        p.say(f"   > {label}")
    except Exception as exc:
        p.skipped.append(f"{label}: {brief(exc)}")
        p.say(f"   ! {label} — {brief(exc)}")


def cancel_order(p: Provisioner, order_id: Optional[int], label: str) -> None:
    """Cancel a sales order, answering the confirmation wizard Odoo raises for
    a quotation that has already been sent to the customer."""
    if p.dry_run or not order_id or order_id < 0:
        p.say(f"   > {label} (would cancel)")
        return
    try:
        state = p.ex("sale.order", "read", [order_id], fields=["state"])
        if state and state[0]["state"] == "cancel":
            p.say(f"   = {label} (already cancelled)")
            return
        result = p.ex("sale.order", "action_cancel", [order_id])
        if isinstance(result, dict) and result.get("res_model") == "sale.order.cancel":
            ctx = result.get("context") or {}
            ctx.setdefault("default_order_id", order_id)
            wid = p.ex("sale.order.cancel", "create", {"order_id": order_id},
                       context=ctx)
            p.ex("sale.order.cancel", "action_cancel", [wid], context=ctx)
        p.say(f"   > {label}")
    except Exception as exc:
        p.skipped.append(f"{label}: {brief(exc)}")
        p.say(f"   ! {label} — {brief(exc)}")


def order_lines(p: Provisioner, refs: dict, spec: list) -> list:
    """Build sale order lines, carrying the cost onto each line so sale_margin
    can report the margin at steps 3 and 11."""
    lines = []
    for key, qty, price, cost, discount in spec:
        variant = product_variant(p, refs["product"].get(key))
        if not variant:
            continue
        lines.append((0, 0, {
            "product_id": variant, "product_uom_qty": qty,
            "price_unit": price, "purchase_price": cost,
            "discount": discount,
        }))
    return lines


def make_enquiry(p: Provisioner, refs: dict, users: dict, name: str,
                 customer_key: str, stage: str, revenue: float,
                 required_in: int, description: str,
                 owner: str = "sales") -> Optional[int]:
    """Step 1 — register the enquiry / RFQ."""
    partner = refs["customer"].get(customer_key)
    vals = {
        "name": name, "type": "opportunity", "partner_id": partner,
        "expected_revenue": revenue, "priority": "2",
        "stage_id": refs["stage"].get(stage),
        "team_id": refs.get("team"), "user_id": users.get(owner),
        "x_required_by": d(required_in),
        "x_estimator_id": users.get("estimation"),
        "date_deadline": d(required_in),
        "description": description,
    }
    return p.ensure("crm.lead", [("name", "=", name)], vals, f"enquiry · {name}")


def make_quote(p: Provisioner, refs: dict, users: dict, ref: str,
               customer_key: str, spec: list, ordered_days_ago: int,
               validity_in: int, owner: str = "sales",
               client_po: str = "", approved: bool = False,
               origin: str = "", revision_of: Optional[int] = None) -> Optional[int]:
    """Steps 3-5 — cost sheet, quotation, validity period."""
    vals = {
        "partner_id": refs["customer"].get(customer_key),
        "user_id": users.get(owner), "team_id": refs.get("team"),
        "date_order": dt(-ordered_days_ago),
        "validity_date": d(validity_in),
        "client_order_ref": client_po or False,
        "origin": origin or False,
        "x_cost_sheet_ref": ref,
        "x_margin_approved": approved,
        "x_revision_of": revision_of or False,
        "order_line": order_lines(p, refs, spec),
    }
    return p.ensure("sale.order", [("x_cost_sheet_ref", "=", ref)], vals,
                    f"quotation · {ref} ({customer_key})")


def make_purchase(p: Provisioner, refs: dict, users: dict, ref: str,
                  supplier_key: str, spec: list, ordered_days_ago: int,
                  origin: str = "", direct_ship: bool = False) -> Optional[int]:
    """Step 8 — the vendor purchase order."""
    lines = []
    for key, qty, price in spec:
        variant = product_variant(p, refs["product"].get(key))
        if not variant:
            continue
        lines.append((0, 0, {"product_id": variant, "product_qty": qty,
                             "price_unit": price,
                             "date_planned": dt(-ordered_days_ago + 14)}))
    vals = {"partner_id": refs["supplier"].get(supplier_key),
            "partner_ref": ref, "date_order": dt(-ordered_days_ago),
            "origin": origin or False, "user_id": users.get("estimation"),
            "x_direct_ship": direct_ship, "order_line": lines}
    return p.ensure("purchase.order", [("partner_ref", "=", ref)], vals,
                    f"purchase order · {ref} ({supplier_key})")


def advance(p: Provisioner, model: str, method: str, rec_id: Optional[int],
            label: str, states: tuple, field: str = "state") -> None:
    """Fire a workflow transition only when the record is in a state that
    accepts it. Records are idempotent through `ensure`; transitions need
    this, or a re-run reports "already confirmed" as a failure."""
    if p.dry_run or not rec_id or rec_id < 0:
        p.say(f"   > {label} (would call {model}.{method})")
        return
    try:
        rec = p.ex(model, "read", [rec_id], fields=[field])
    except Exception as exc:
        p.skipped.append(f"{label}: {brief(exc)}")
        p.say(f"   ! {label} — {brief(exc)}")
        return
    current = rec[0][field] if rec else None
    if current not in states:
        p.say(f"   = {label} (already past this step; {field}={current})")
        return
    p.call(model, method, [rec_id], label)


def outgoing_pickings(p: Provisioner, order_id: int) -> list:
    """The deliveries a confirmed sales order generated."""
    if p.dry_run or not order_id or order_id < 0:
        return []
    try:
        return p.ex("stock.picking", "search",
                    [("sale_id", "=", order_id),
                     ("picking_type_code", "=", "outgoing"),
                     ("state", "not in", ["cancel"])], order="id asc")
    except Exception:
        return []


def seed_transactions(p: Provisioner, refs: dict, users: dict) -> None:
    """Eight scenarios that between them walk every branch of the chart."""

    # ── A · DEMO-01 — the full cycle, steps 1 through 11 ─────────────────────
    p.say("\n   ── Scenario A · DEMO-01 Al Mazroui — complete enquiry to cash")
    lead_a = make_enquiry(
        p, refs, users, "ENQ/2026/001 — Pump skid replacement (Al Mazroui)",
        "almazroui", "Won", 68000.0, -20,
        "Replacement of two 75 kW centrifugal pump skids including "
        "commissioning. Technical specification attached to the RFQ.")
    quote_a = make_quote(
        p, refs, users, "DEMO-01", "almazroui",
        [("pump", 2, 5880.0, 4200.0, 0.0),
         ("valve", 6, 465.0, 310.0, 5.0),
         ("commiss", 1, 3500.0, 1800.0, 0.0),
         ("freight", 1, 850.0, 600.0, 0.0)],
        ordered_days_ago=40, validity_in=-10, client_po="PO-ALM-88214",
        approved=True, origin="ENQ/2026/001")
    advance(p, "sale.order", "action_quotation_sent", quote_a,
            "DEMO-01 · step 5 — quotation submitted to the customer", ("draft",))
    advance(p, "sale.order", "action_confirm", quote_a,
            "DEMO-01 · step 7 — customer PO verified, sales order confirmed",
            ("draft", "sent"))
    po_a = make_purchase(
        p, refs, users, "DEMO-01-PO", "nordic",
        [("pump", 2, 3980.0)], ordered_days_ago=36, origin="DEMO-01")
    advance(p, "purchase.order", "button_confirm", po_a,
            "DEMO-01 · step 8 — supplier PO issued to Nordic Pump Works",
            ("draft", "sent"))
    if not p.dry_run and po_a and po_a > 0:
        receipts = p.ex("stock.picking", "search",
                        [("purchase_id", "=", po_a), ("state", "!=", "cancel")])
        for pick in receipts:
            validate_picking(p, pick, "DEMO-01 · step 8 — goods received into stock")
    for pick in outgoing_pickings(p, quote_a):
        validate_picking(p, pick, "DEMO-01 · step 9 — delivered in full")
        p.write("stock.picking", [pick],
                {"x_pod_received": True, "x_pod_date": d(-12),
                 "x_pod_signed_by": "H. Al Mazroui (Site Engineer)"},
                "DEMO-01 · step 9 — signed POD captured")
    inv_a = invoice_order(p, quote_a, "DEMO-01 · step 10 — customer invoice posted",
                          inv_date_offset=-12, due_offset=18)
    pay_invoice(p, inv_a, "DEMO-01 · step 10 — payment received and reconciled",
                date_offset=-3)

    # ── B · DEMO-02 — partial delivery and partial payment ──────────────────
    p.say("\n   ── Scenario B · DEMO-02 Gulf Petrochem — partial delivery, partly paid")
    make_enquiry(p, refs, users, "ENQ/2026/002 — Valve and pipe package (Gulf Petrochem)",
                 "gulfpetro", "Won", 24000.0, 5,
                 "Valves, flanges and 316L pipe for the de-bottlenecking "
                 "project. Phased delivery acceptable.")
    quote_b = make_quote(
        p, refs, users, "DEMO-02", "gulfpetro",
        [("valve", 20, 465.0, 310.0, 0.0),
         ("pipe", 40, 252.0, 180.0, 2.5),
         ("flange", 20, 142.0, 95.0, 0.0)],
        ordered_days_ago=25, validity_in=5, client_po="GPS/PO/4471",
        approved=True, origin="ENQ/2026/002")
    advance(p, "sale.order", "action_confirm", quote_b,
            "DEMO-02 · step 7 — sales order confirmed", ("draft", "sent"))
    picks_b = outgoing_pickings(p, quote_b)
    if picks_b:
        validate_picking(p, picks_b[0],
                         "DEMO-02 · step 9 — first drop delivered (60%), backorder raised",
                         ratio=0.6)
        p.write("stock.picking", [picks_b[0]],
                {"x_pod_received": True, "x_pod_date": d(-6),
                 "x_pod_signed_by": "S. Rahman (Warehouse)"},
                "DEMO-02 · step 9 — POD for the first drop")
        for pick in outgoing_pickings(p, quote_b)[1:]:
            p.write("stock.picking", [pick], {"x_delivery_status": "planned"},
                    "DEMO-02 · step 9 — backorder scheduled")
    inv_b = invoice_order(p, quote_b, "DEMO-02 · step 10 — invoice for what was delivered",
                          inv_date_offset=-6, due_offset=24)
    pay_invoice(p, inv_b, "DEMO-02 · step 10 — part payment on account",
                amount=4000.0, date_offset=-2)

    # ── C · DEMO-03 — held at the margin approval gate (step 4) ─────────────
    p.say("\n   ── Scenario C · DEMO-03 Emirates Steel — waiting on margin approval")
    make_enquiry(p, refs, users, "ENQ/2026/003 — Motor and gauge supply (Emirates Steel)",
                 "emsteel", "Estimation", 18000.0, 12,
                 "Explosion-proof motor with instrumentation. Customer is "
                 "price-sensitive; competitor quote in play.")
    make_quote(
        p, refs, users, "DEMO-03", "emsteel",
        # Priced thin on purpose: ~6% margin plus a 15% line discount, so both
        # halves of the step 4 gate fire and the quote lands in Pending Approval.
        [("motor", 2, 5900.0, 5600.0, 0.0),
         ("gauge", 10, 60.0, 45.0, 15.0)],
        ordered_days_ago=4, validity_in=26, origin="ENQ/2026/003")

    # ── D · DEMO-04 — submitted, awaiting the customer decision (step 6) ────
    p.say("\n   ── Scenario D · DEMO-04 Desert Rock — submitted, awaiting decision")
    make_enquiry(p, refs, users, "ENQ/2026/004 — Pipe spools and flanges (Desert Rock)",
                 "desert", "Quotation", 9500.0, 20,
                 "Spool fabrication inputs for the camp expansion.")
    quote_d = make_quote(
        p, refs, users, "DEMO-04", "desert",
        [("pipe", 25, 252.0, 180.0, 0.0), ("flange", 14, 142.0, 95.0, 0.0)],
        ordered_days_ago=9, validity_in=21, approved=True,
        origin="ENQ/2026/004")
    advance(p, "sale.order", "action_quotation_sent", quote_d,
            "DEMO-04 · step 5 — quotation submitted, follow-up cadence started",
            ("draft",))

    # ── E · DEMO-05 — lost, with a reason (step 6, Lost branch) ─────────────
    p.say("\n   ── Scenario E · DEMO-05 Sharjah Water — enquiry lost")
    lead_e = make_enquiry(
        p, refs, users, "ENQ/2026/005 — Pump overhaul tender (Sharjah Water)",
        "sharjah", "Quotation", 42000.0, -5,
        "Public tender for pump overhaul. Lost on price against an "
        "incumbent framework supplier.")
    if lead_e and lead_e > 0 and not p.dry_run:
        reason = refs["lost"].get("Price too high")
        p.call("crm.lead", "action_set_lost", [lead_e],
               "DEMO-05 · step 6 — marked lost, reason recorded",
               lost_reason_id=reason)

    # ── F · DEMO-06 — revision / requote (step 6, Revision branch) ──────────
    p.say("\n   ── Scenario F · DEMO-06 Al Mazroui — re-cost and requote")
    original = make_quote(
        p, refs, users, "DEMO-06-R0", "almazroui",
        [("pump", 1, 5880.0, 4200.0, 0.0), ("commiss", 1, 3500.0, 1800.0, 0.0)],
        ordered_days_ago=16, validity_in=-2, origin="ENQ/2026/006")
    advance(p, "sale.order", "action_quotation_sent", original,
            "DEMO-06 · step 5 — original quotation submitted", ("draft",))
    cancel_order(p, original,
                 "DEMO-06 · step 6 — customer asked for a revision")
    make_quote(
        p, refs, users, "DEMO-06-R1", "almazroui",
        # Re-costed against a cheaper freight route, so the margin survives
        # the price cut the customer asked for.
        [("pump", 1, 5600.0, 3980.0, 0.0), ("commiss", 1, 3300.0, 1800.0, 0.0)],
        ordered_days_ago=3, validity_in=27, approved=True,
        origin="ENQ/2026/006 (revision 1)", revision_of=original)

    # ── G · DEMO-07 — overdue invoice and a collection chase (step 10) ──────
    p.say("\n   ── Scenario G · DEMO-07 Desert Rock — overdue invoice in collection")
    quote_g = make_quote(
        p, refs, users, "DEMO-07", "desert",
        [("valve", 8, 465.0, 310.0, 0.0), ("gauge", 12, 72.0, 45.0, 0.0)],
        ordered_days_ago=70, validity_in=-40, client_po="DRC-PO-2291",
        approved=True, origin="ENQ/2026/007")
    advance(p, "sale.order", "action_confirm", quote_g,
            "DEMO-07 · step 7 — sales order confirmed", ("draft", "sent"))
    for pick in outgoing_pickings(p, quote_g):
        validate_picking(p, pick, "DEMO-07 · step 9 — delivered")
        p.write("stock.picking", [pick],
                {"x_pod_received": True, "x_pod_date": d(-62),
                 "x_pod_signed_by": "A. Khan (Store)"},
                "DEMO-07 · step 9 — POD captured")
    inv_g = invoice_order(p, quote_g,
                          "DEMO-07 · step 10 — invoice posted (now overdue)",
                          inv_date_offset=-62, due_offset=-32)

    # ── H · early-stage enquiries, so the step 1-2 pipeline is not empty ────
    p.say("\n   ── Scenario H · live enquiries at steps 1-2")
    make_enquiry(p, refs, users, "ENQ/2026/008 — Spare parts call-off (Gulf Petrochem)",
                 "gulfpetro", "New", 7200.0, 25,
                 "Annual spares call-off. Awaiting assignment to an estimator.",
                 owner="sales")
    make_enquiry(p, refs, users, "ENQ/2026/009 — Instrumentation package (Emirates Steel)",
                 "emsteel", "Under Review", 15400.0, 18,
                 "Technical review in progress; two line items need a "
                 "supplier substitution.", owner="estimation")
    make_enquiry(p, refs, users, "ENQ/2026/010 — Pipe and fittings (Sharjah Water)",
                 "sharjah", "Estimation", 31000.0, 30,
                 "Awaiting firm supplier prices on 316L pipe before costing.",
                 owner="estimation")
    # One enquiry left deliberately unowned and already past its date, so the
    # unassigned/overdue RFQ alert has something real to raise.
    orphan = p.ensure(
        "crm.lead",
        [("name", "=", "ENQ/2026/011 — Unassigned walk-in enquiry")],
        {"name": "ENQ/2026/011 — Unassigned walk-in enquiry",
         "type": "opportunity", "partner_id": refs["customer"].get("desert"),
         "expected_revenue": 4800.0, "stage_id": refs["stage"].get("New"),
         "team_id": refs.get("team"), "user_id": False,
         "x_required_by": d(-3), "date_deadline": d(-3),
         "description": "Walk-in enquiry with no owner and a lapsed required-by "
                        "date — this is what the unassigned/overdue RFQ alert finds."},
        "enquiry · ENQ/2026/011 (deliberately unassigned)")
    if orphan and orphan > 0 and not p.dry_run:
        # The assignment automation would adopt it the moment an owner is set,
        # so clear the owner again after creation defaults put one there.
        p.ex("crm.lead", "write", [orphan], {"user_id": False})

    # Step 8's purchase requisition, where the module provides one.
    if p.has_model("purchase.requisition"):
        lines = []
        for key, qty, price in (("valve", 20, 295.0), ("flange", 20, 88.0)):
            variant = product_variant(p, refs["product"].get(key))
            if variant:
                lines.append((0, 0, {"product_id": variant, "product_qty": qty,
                                     "price_unit": price}))
        # No stable text key on this model in 19 (`origin` is gone and the
        # name is a sequence), so key off "does the demo already have one".
        if p.dry_run or not p.find("purchase.requisition", []):
            p.ensure("purchase.requisition", [("id", "=", 0)],
                     {"user_id": users.get("estimation"),
                      "date_end": dt(7), "line_ids": lines},
                     "purchase requisition · DEMO-02 (step 8)")
        else:
            p.say("   = purchase requisition (exists)")
    _ = lead_a, inv_g   # kept for readability of the scenario flow


# ── phase 5b: historical volume ─────────────────────────────────────────────
# Months of closed business behind the eight showcase scenarios, so the step 11
# reporting, the ageing and the cash forecast have a real population to work
# on rather than seven orders. Everything is derived from the record's own
# reference, so the same reference always produces the same order — which is
# what keeps a re-run idempotent without storing any state.

def roll(token: str, modulus: int) -> int:
    """A stable pseudo-random integer for a reference. Deterministic across
    runs and machines, unlike random.seed, which would drift if the call order
    ever changed."""
    return int(hashlib.md5(token.encode()).hexdigest(), 16) % modulus


# Baskets a trading company actually ships, as (product key, low qty, high qty).
BASKETS = [
    [("valve", 4, 20), ("flange", 4, 20), ("gasket", 10, 40), ("bolts", 10, 30)],
    [("pump_sm", 1, 4), ("sealkit", 1, 4), ("coupling", 1, 3), ("commiss", 1, 1)],
    [("pipe", 10, 60), ("expjoint", 2, 8), ("strainer", 1, 6)],
    [("ctrlvlv", 1, 3), ("actuator", 1, 3), ("transmit", 2, 8), ("calib", 1, 1)],
    [("motor", 1, 3), ("switchgr", 1, 2), ("cable", 50, 300)],
    [("bfvalve", 2, 10), ("gauge", 4, 16), ("bearing", 2, 10)],
    [("pump", 1, 3), ("freight", 1, 1), ("survey", 1, 1)],
    [("mainten", 1, 1), ("calib", 1, 2), ("sealkit", 2, 6)],
]


def history_lines(p: Provisioner, refs: dict, ref: str) -> list:
    """A deterministic basket for this reference, priced at list with the
    product's own cost carried onto the line for margin reporting."""
    basket = BASKETS[roll(ref + "basket", len(BASKETS))]
    spec = []
    for key, low, high in basket:
        tmpl = refs["product"].get(key)
        if not tmpl:
            continue
        qty = low + roll(ref + key, max(high - low, 1))
        meta = next((x for x in PRODUCTS if x[0] == key), None)
        if not meta:
            continue
        _k, _name, _kind, cost, price, _code = meta
        # A little price movement, so not every deal lands on the same margin.
        discount = (0.0, 0.0, 2.5, 5.0)[roll(ref + key + "disc", 4)]
        spec.append((key, qty, price, cost, discount))
    return order_lines(p, refs, spec)


def seed_history(p: Provisioner, refs: dict, users: dict,
                 months: int, per_month: int) -> None:
    """Closed and in-flight business across the past `months` months."""
    cust = sorted(refs["customer"])
    supp = sorted(refs["supplier"])
    sellers = [k for k in ("sales", "estimation", "manager") if users.get(k)]
    made = 0
    for back in range(months, 0, -1):
        stamp = (TODAY - timedelta(days=back * 30)).strftime("%Y%m")
        for i in range(per_month):
            ref = f"HIST-{stamp}-{i:02d}"
            lines = history_lines(p, refs, ref)
            if not lines:
                continue
            days_ago = back * 30 - roll(ref + "day", 25)
            customer = cust[roll(ref + "cust", len(cust))]
            owner = sellers[roll(ref + "own", len(sellers))] if sellers else "sales"
            fate = roll(ref + "fate", 10)

            order = p.ensure("sale.order", [("x_cost_sheet_ref", "=", ref)], {
                "partner_id": refs["customer"].get(customer),
                "user_id": users.get(owner), "team_id": refs.get("team"),
                "date_order": dt(-days_ago), "validity_date": d(-days_ago + 30),
                "client_order_ref": f"PO-{stamp}-{i:02d}",
                "x_cost_sheet_ref": ref, "x_margin_approved": True,
                "order_line": lines,
            }, f"history · {ref} ({customer})")
            if not order:
                continue
            made += 1

            if fate == 0:      # still an open quotation
                advance(p, "sale.order", "action_quotation_sent", order,
                        f"history · {ref} quotation sent", ("draft",))
                continue
            if fate == 1:      # lost
                advance(p, "sale.order", "action_cancel", order,
                        f"history · {ref} cancelled", ("draft", "sent"))
                continue

            advance(p, "sale.order", "action_confirm", order,
                    f"history · {ref} confirmed", ("draft", "sent"))
            for pick in outgoing_pickings(p, order):
                validate_picking(p, pick, f"history · {ref} delivered")
                p.write("stock.picking", [pick],
                        {"x_pod_received": True, "x_pod_date": d(-days_ago + 7),
                         "x_pod_signed_by": "Site representative"},
                        f"history · {ref} POD")
            inv = invoice_order(p, order, f"history · {ref} invoiced",
                                inv_date_offset=-days_ago + 8,
                                due_offset=-days_ago + 38)
            # Most are settled; the recent tail stays open so the ageing report
            # and the collection alerts have live receivables to show.
            if inv and fate >= 3 and days_ago > 45:
                pay_invoice(p, inv, f"history · {ref} paid",
                            date_offset=-days_ago + 34)
            elif inv and fate == 2:
                pay_invoice(p, inv, f"history · {ref} part paid",
                            amount=round(500 + roll(ref + "amt", 2000), 2),
                            date_offset=-days_ago + 30)

            # Every third order gets its supply side too, so payables, the
            # vendor ledger and the cash forecast are not one-sided.
            if roll(ref + "buy", 3) == 0:
                vendor = supp[roll(ref + "sup", len(supp))]
                pref = f"{ref}-PO"
                basket = BASKETS[roll(ref + "basket", len(BASKETS))]
                pspec = []
                for key, low, _high in basket[:2]:
                    meta = next((x for x in PRODUCTS if x[0] == key), None)
                    if meta:
                        pspec.append((key, low, round(meta[3] * 0.95, 2)))
                po = make_purchase(p, refs, users, pref, vendor, pspec,
                                   ordered_days_ago=days_ago + 20, origin=ref)
                advance(p, "purchase.order", "button_confirm", po,
                        f"history · {pref} issued", ("draft", "sent"))
                if po and po > 0 and not p.dry_run:
                    for rcv in (p.ex("stock.picking", "search",
                                     [("purchase_id", "=", po),
                                      ("state", "!=", "cancel")]) or []):
                        validate_picking(p, rcv, f"history · {pref} received")
                    bill_purchase(p, po, f"history · {pref} billed",
                                  days_ago - 5)
    p.say(f"   ~ historical orders present: {made}")


def bill_purchase(p: Provisioner, po_id: Optional[int], label: str,
                  days_ago: int) -> None:
    """Vendor bill from a purchase order, posted — this is what gives the demo
    a payables side and makes the cash forecast alert meaningful."""
    if p.dry_run or not po_id or po_id < 0:
        p.say(f"   > {label} (would bill)")
        return
    try:
        existing = p.ex("purchase.order", "read", [po_id], fields=["invoice_ids"])
        if existing and existing[0]["invoice_ids"]:
            return
        p.ex("purchase.order", "action_create_invoice", [po_id])
        refreshed = p.ex("purchase.order", "read", [po_id], fields=["invoice_ids"])
        for bill in (refreshed[0]["invoice_ids"] if refreshed else []):
            p.ex("account.move", "write", [bill],
                 {"invoice_date": d(-days_ago),
                  "invoice_date_due": d(-days_ago + 30)})
            p.ex("account.move", "action_post", [bill])
        p.say(f"   > {label}")
    except Exception as exc:
        p.skipped.append(f"{label}: {brief(exc)}")
        p.say(f"   ! {label} — {brief(exc)}")


# ── phase 6: verification ────────────────────────────────────────────────────
# What each step of the chart should look like once the script has run, as
# (step, label, model, domain). The report is the proof the demo is walkable.
CHECKS = [
    ("1",  "Enquiries / RFQs in the pipeline", "crm.lead",
     [("type", "=", "opportunity")]),
    ("1",  "…unassigned or past required-by", "crm.lead",
     [("type", "=", "opportunity"), ("user_id", "=", False)]),
    ("2",  "Supplier price list entries", "product.supplierinfo", []),
    ("2",  "…with a lapsed validity", "product.supplierinfo",
     [("date_end", "<", d(0))]),
    ("3",  "Quotations carrying a cost sheet", "sale.order",
     [("x_cost_sheet_ref", "!=", False)]),
    ("4",  "Held for margin / discount approval", "sale.order",
     [("x_quote_status", "=", "pending_approval")]),
    ("4",  "Approved quotations", "sale.order", [("x_margin_approved", "=", True)]),
    ("5",  "Quotations submitted to a customer", "sale.order",
     [("state", "=", "sent")]),
    ("6",  "Enquiries lost with a reason", "crm.lead",
     [("active", "=", False), ("lost_reason_id", "!=", False)]),
    ("6",  "Revised quotations", "sale.order", [("x_revision_of", "!=", False)]),
    ("7",  "Confirmed sales orders", "sale.order", [("state", "in", ["sale", "done"])]),
    ("7",  "…carrying the customer PO reference", "sale.order",
     [("state", "in", ["sale", "done"]), ("client_order_ref", "!=", False)]),
    ("8",  "Purchase orders issued", "purchase.order",
     [("state", "in", ["purchase", "done"])]),
    ("8",  "Goods receipts completed", "stock.picking",
     [("picking_type_code", "=", "incoming"), ("state", "=", "done")]),
    ("9",  "Deliveries completed", "stock.picking",
     [("picking_type_code", "=", "outgoing"), ("state", "=", "done")]),
    ("9",  "…with the POD captured", "stock.picking",
     [("x_pod_received", "=", True)]),
    ("9",  "Open backorders / planned deliveries", "stock.picking",
     [("picking_type_code", "=", "outgoing"), ("state", "not in", ["done", "cancel"])]),
    ("10", "Customer invoices posted", "account.move",
     [("move_type", "=", "out_invoice"), ("state", "=", "posted")]),
    ("10", "…overdue", "account.move",
     [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
      ("invoice_date_due", "<", d(0)), ("payment_state", "in", ["not_paid", "partial"])]),
    ("10", "…partially paid", "account.move",
     [("move_type", "=", "out_invoice"), ("payment_state", "=", "partial")]),
    ("10", "…paid and reconciled", "account.move",
     [("move_type", "=", "out_invoice"), ("payment_state", "in", ["paid", "in_payment"])]),
    ("10", "Vendor bills posted", "account.move",
     [("move_type", "=", "in_invoice"), ("state", "=", "posted")]),
    ("10", "Payments registered", "account.payment", []),
    ("11", "Chart of accounts", "account.account", []),
    ("11", "Journal entries", "account.move", [("state", "=", "posted")]),
    ("11", "Journals", "account.journal", []),
    ("11", "Automation rules (approvals, POD, statuses)", "base.automation", []),
    ("11", "Scheduled alerts and exceptions", "ir.cron",
     [("name", "like", "E2C %")]),
    ("11", "Open activities across the flow", "mail.activity", []),
]


def verify(p: Provisioner) -> list:
    """Count what actually landed, step by step."""
    rows = []
    for step, label, model, domain in CHECKS:
        try:
            rows.append((step, label, p.ex(model, "search_count", domain)))
        except Exception as exc:
            rows.append((step, label, f"n/a ({type(exc).__name__})"))
    return rows


def render_report(p: Provisioner, rows: list, db: str, url: str) -> str:
    out = [
        "", "=" * 74,
        f"  Enquiry-to-Cash demonstration database · {db}",
        f"  {url}",
        "=" * 74, "",
        f"  Records created: {p.created}    already present: {p.reused}", "",
    ]
    last = None
    for step, label, count in rows:
        if step != last:
            out.append(f"  Step {step}")
            last = step
        out.append(f"    {label:.<56} {count}")
    if p.skipped:
        out += ["", "  Not applied (review these):"]
        for item in p.skipped:
            out.append(f"    - {item}")
    out += ["", "  Log in as admin, or as one of the demo roles:",
            "    layla.sales@demo.local     — raises enquiries and quotations",
            "    omar.estimation@demo.local — costs and sources",
            "    rania.manager@demo.local   — approves margin and discounts",
            "    tariq.warehouse@demo.local — dispatch and POD",
            "    hana.finance@demo.local    — invoicing and collection", ""]
    return "\n".join(out)


# ── CLI ──────────────────────────────────────────────────────────────────────
PHASES = ["create", "install", "config", "fields", "automation", "alerts",
          "seed", "history", "verify"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision an Odoo demonstration database for the "
                    "eleven-step Enquiry-to-Cash process.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("db", help="database name to create or configure")
    parser.add_argument("--url", help="Odoo base URL (default: ODOO_URL or "
                                      "http://localhost:8069)")
    parser.add_argument("--admin-user", default=None,
                        help="login to work as (default: ODOO_USER or admin)")
    parser.add_argument("--admin-password", default=None,
                        help="password for that login, and the password set on "
                             "a database this script creates")
    parser.add_argument("--master-password", default=None,
                        help="Odoo database master password, needed only to "
                             "create a database (or set C2P_ODOO_MASTER_PWD)")
    parser.add_argument("--no-create", action="store_true",
                        help="do not create the database; configure and seed "
                             "one that already exists")
    parser.add_argument("--country", default="AE",
                        help="country code for the fiscal localization and "
                             "chart of accounts (default: AE)")
    parser.add_argument("--lang", default="en_US", help="database language")
    parser.add_argument("--company", default="C2P Trading & Supply Demo LLC",
                        help="company name for the demo")
    parser.add_argument("--currency", default="AED", help="company currency")
    parser.add_argument("--demo-user-password", default="demo1234",
                        help="password for the five demo role users")
    parser.add_argument("--odoo-demo-data", action="store_true",
                        help="also load Odoo's own demo data into the new "
                             "database (off by default — this script seeds its own)")
    parser.add_argument("--months", type=int, default=6, metavar="N",
                        help="months of historical business to seed "
                             "(default 6; 0 disables the history phase)")
    parser.add_argument("--per-month", type=int, default=6, metavar="N",
                        help="orders per historical month (default 6)")
    parser.add_argument("--only", metavar="PHASES",
                        help="run only these comma-separated phases: "
                             + ", ".join(PHASES))
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would happen; write nothing")
    parser.add_argument("--json", action="store_true",
                        help="emit the verification counts as JSON")
    args = parser.parse_args()

    load_env(ROOT / "delivery_api" / ".env")
    url = args.url or os.environ.get("ODOO_URL") or "http://localhost:8069"
    user = args.admin_user or os.environ.get("ODOO_USER") or "admin"
    password = (args.admin_password or os.environ.get("ODOO_PASSWORD")
                or "admin")
    master = args.master_password or os.environ.get("C2P_ODOO_MASTER_PWD") or ""

    phases = PHASES
    if args.only:
        phases = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [x for x in phases if x not in PHASES]
        if unknown:
            parser.error(f"unknown phase(s): {', '.join(unknown)}; "
                         f"choose from {', '.join(PHASES)}")
    if args.no_create and "create" in phases:
        phases = [x for x in phases if x != "create"]

    print(f"\nEnquiry-to-Cash demo provisioning → {url} / {args.db}"
          + ("   [DRY RUN — nothing will be written]" if args.dry_run else ""))

    if "create" in phases:
        print("\n[1/9] Database")
        try:
            print("   " + create_database(url, args.db, master, password,
                                          args.country, args.lang,
                                          args.odoo_demo_data, args.dry_run))
        except SystemExit:
            raise
        except Exception as exc:
            print(f"   ! database creation failed — {brief(exc)}", file=sys.stderr)
            return 1

    p = Provisioner(args.db, url, user, password, dry_run=args.dry_run)
    try:
        if not args.dry_run:
            p.uid          # fail fast and clearly on bad credentials
    except Exception as exc:
        print(f"\nCannot authenticate against '{args.db}': {brief(exc)}",
              file=sys.stderr)
        print("Check ODOO_URL / ODOO_USER / ODOO_PASSWORD, or pass "
              "--admin-user / --admin-password.", file=sys.stderr)
        return 1

    refs: dict = {}
    users: dict = {}
    try:
        if "install" in phases:
            print("\n[2/9] Applications")
            install_modules(p, MODULES)
        if "config" in phases:
            print("\n[3/9] Standard configuration")
            apply_settings(p)
            company_id = configure_company(p, args.company, args.currency)
            enable_accounting(p, company_id)
            users = ensure_users(p, args.demo_user_password)
            refs = ensure_master_data(p)
            refs.update(ensure_pipeline(p, users))
        if "fields" in phases:
            print("\n[4/9] Studio-equivalent fields")
            ensure_manual_fields(p)
        if "automation" in phases:
            print("\n[5/9] Automation rules")
            ensure_automations(p)
        if "alerts" in phases:
            print("\n[6/9] Scheduled alerts and exceptions")
            ensure_alerts(p)
        if "seed" in phases:
            print("\n[7/9] Demonstration transactions")
            if not refs:
                # Running --only seed against an already-configured database:
                # rebuild the references without re-applying the settings.
                users = ensure_users(p, args.demo_user_password)
                refs = ensure_master_data(p)
                refs.update(ensure_pipeline(p, users))
            stock_in(p, refs)
            seed_transactions(p, refs, users)
        if "history" in phases and args.months > 0:
            print(f"\n[8/9] Historical volume "
                  f"({args.months} months x {args.per_month} orders)")
            if not refs:
                users = ensure_users(p, args.demo_user_password)
                refs = ensure_master_data(p)
                refs.update(ensure_pipeline(p, users))
                stock_in(p, refs)
            seed_history(p, refs, users, args.months, args.per_month)
    except KeyboardInterrupt:
        print("\ninterrupted — re-run to continue; every step is idempotent",
              file=sys.stderr)
        return 130

    if "verify" in phases and not args.dry_run:
        print("\n[9/9] Verification")
        rows = verify(p)
        if args.json:
            print(json.dumps({"db": args.db, "url": url,
                              "created": p.created, "reused": p.reused,
                              "skipped": p.skipped,
                              "checks": [{"step": s, "label": l, "count": c}
                                         for s, l, c in rows]},
                             indent=2, default=str))
        else:
            print(render_report(p, rows, args.db, url))
        return 1 if any(isinstance(c, str) for _, _, c in rows) and p.skipped else 0

    if args.dry_run:
        print(f"\nDry run complete — {abs(p._fake)} records would be created, "
              f"{p.reused} already exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
