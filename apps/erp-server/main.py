"""Mumtaz ERP Server — FastAPI + PostgreSQL backend."""
import os, base64
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from typing import Optional, List, Any

import psycopg2, psycopg2.extras
from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

import odoo_client as odoo
from odoo_client import OdooError, OdooConnectionError

load_dotenv()

DB_URL  = os.getenv("ERP_DATABASE_URL", "postgresql://erp_user:erp_pass@localhost/mumtaz_erp")
SECRET  = os.getenv("ERP_SECRET", "mumtaz-erp-secret-change-me")
ALGO    = "HS256"

pwd_ctx = CryptContext(schemes=["bcrypt"])
app     = FastAPI(title="Mumtaz ERP", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# ── Database ──────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = psycopg2.connect(DB_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def dictcur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def fetchall(conn, sql, params=()):
    c = dictcur(conn)
    c.execute(sql, params)
    return [dict(r) for r in c.fetchall()]

def fetchone(conn, sql, params=()):
    c = dictcur(conn)
    c.execute(sql, params)
    row = c.fetchone()
    return dict(row) if row else None

def execute(conn, sql, params=()):
    c = dictcur(conn)
    c.execute(sql, params)
    try:
        return dict(c.fetchone())
    except Exception:
        return None


# ── Auth ──────────────────────────────────────────────────────
def make_token(user_id: int, company_id: Optional[int], is_super: bool = False) -> str:
    exp = datetime.utcnow() + timedelta(days=30)
    return jwt.encode({"sub": str(user_id), "cid": company_id, "sup": is_super, "exp": exp}, SECRET, algorithm=ALGO)

def get_user(authorization: str = Header(...)):
    try:
        scheme, token = authorization.split()
        assert scheme.lower() == "bearer"
        p = jwt.decode(token, SECRET, algorithms=[ALGO])
        return {"user_id": int(p["sub"]), "company_id": p.get("cid"), "is_super": bool(p.get("sup", False))}
    except Exception:
        raise HTTPException(401, "Not authenticated")

def require_super(ctx=Depends(get_user)):
    if not ctx.get("is_super"):
        raise HTTPException(403, "Super admin access required")
    return ctx


# ── ZATCA QR (Phase 1 TLV) ────────────────────────────────────
def gen_zatca_qr(seller: str, vat: str, ts: str, total: float, tax: float) -> str:
    def tlv(tag: int, val: str) -> bytes:
        b = val.encode()
        return bytes([tag, len(b)]) + b
    data = tlv(1, seller) + tlv(2, vat or "0000000000000") + tlv(3, ts) + \
           tlv(4, f"{total:.2f}") + tlv(5, f"{tax:.2f}")
    return base64.b64encode(data).decode()


# ── Schema ────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
  id SERIAL PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  name_ar     VARCHAR(255),
  vat_number  VARCHAR(50),
  cr_number   VARCHAR(50),
  address     TEXT,
  city        VARCHAR(100),
  country     VARCHAR(100) DEFAULT 'UAE',
  phone       VARCHAR(50),
  email       VARCHAR(255),
  currency    VARCHAR(3)  DEFAULT 'AED',
  created_at  TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(255) NOT NULL,
  email         VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(50)  DEFAULT 'staff',
  company_id    INTEGER REFERENCES companies(id),
  active        BOOLEAN      DEFAULT TRUE,
  created_at    TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  code        VARCHAR(20)  NOT NULL,
  name        VARCHAR(255) NOT NULL,
  type        VARCHAR(50)  NOT NULL,
  parent_id   INTEGER REFERENCES accounts(id),
  reconcile   BOOLEAN DEFAULT FALSE,
  active      BOOLEAN DEFAULT TRUE,
  UNIQUE(company_id, code)
);

CREATE TABLE IF NOT EXISTS partners (
  id            SERIAL PRIMARY KEY,
  company_id    INTEGER REFERENCES companies(id),
  name          VARCHAR(255) NOT NULL,
  name_ar       VARCHAR(255),
  is_customer   BOOLEAN DEFAULT FALSE,
  is_vendor     BOOLEAN DEFAULT FALSE,
  vat_number    VARCHAR(50),
  email         VARCHAR(255),
  phone         VARCHAR(50),
  address       TEXT,
  city          VARCHAR(100),
  country       VARCHAR(100) DEFAULT 'UAE',
  payment_terms INTEGER      DEFAULT 30,
  active        BOOLEAN      DEFAULT TRUE,
  created_at    TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
  id                SERIAL PRIMARY KEY,
  company_id        INTEGER REFERENCES companies(id),
  name              VARCHAR(255) NOT NULL,
  code              VARCHAR(50),
  type              VARCHAR(50)  DEFAULT 'service',
  sale_price        NUMERIC(15,2) DEFAULT 0,
  cost_price        NUMERIC(15,2) DEFAULT 0,
  unit              VARCHAR(50)  DEFAULT 'unit',
  income_account_id  INTEGER REFERENCES accounts(id),
  expense_account_id INTEGER REFERENCES accounts(id),
  active            BOOLEAN DEFAULT TRUE,
  created_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS taxes (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  name        VARCHAR(100) NOT NULL,
  rate        NUMERIC(5,2) NOT NULL,
  type        VARCHAR(50)  DEFAULT 'sale',
  account_id  INTEGER REFERENCES accounts(id),
  active      BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS journals (
  id                SERIAL PRIMARY KEY,
  company_id        INTEGER REFERENCES companies(id),
  name              VARCHAR(100) NOT NULL,
  type              VARCHAR(50)  NOT NULL,
  sequence_prefix   VARCHAR(20),
  sequence_next     INTEGER DEFAULT 1,
  default_account_id INTEGER REFERENCES accounts(id),
  active            BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS moves (
  id              SERIAL PRIMARY KEY,
  company_id      INTEGER REFERENCES companies(id),
  name            VARCHAR(100),
  move_type       VARCHAR(50)  NOT NULL,
  state           VARCHAR(50)  DEFAULT 'draft',
  date            DATE         NOT NULL,
  invoice_date    DATE,
  partner_id      INTEGER REFERENCES partners(id),
  journal_id      INTEGER REFERENCES journals(id),
  currency        VARCHAR(3)   DEFAULT 'AED',
  amount_untaxed  NUMERIC(15,2) DEFAULT 0,
  amount_tax      NUMERIC(15,2) DEFAULT 0,
  amount_total    NUMERIC(15,2) DEFAULT 0,
  amount_residual NUMERIC(15,2) DEFAULT 0,
  payment_state   VARCHAR(50)  DEFAULT 'not_paid',
  due_date        DATE,
  narration       TEXT,
  ref             VARCHAR(100),
  zatca_qr        TEXT,
  created_by      INTEGER REFERENCES users(id),
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS move_lines (
  id           SERIAL PRIMARY KEY,
  move_id      INTEGER REFERENCES moves(id) ON DELETE CASCADE,
  company_id   INTEGER REFERENCES companies(id),
  account_id   INTEGER REFERENCES accounts(id),
  partner_id   INTEGER REFERENCES partners(id),
  name         VARCHAR(500) NOT NULL,
  debit        NUMERIC(15,2) DEFAULT 0,
  credit       NUMERIC(15,2) DEFAULT 0,
  tax_id       INTEGER REFERENCES taxes(id),
  date_maturity DATE
);

CREATE TABLE IF NOT EXISTS invoice_lines (
  id              SERIAL PRIMARY KEY,
  move_id         INTEGER REFERENCES moves(id) ON DELETE CASCADE,
  product_id      INTEGER REFERENCES products(id),
  name            VARCHAR(500) NOT NULL,
  quantity        NUMERIC(15,3) DEFAULT 1,
  unit_price      NUMERIC(15,2) DEFAULT 0,
  discount        NUMERIC(5,2)  DEFAULT 0,
  tax_id          INTEGER REFERENCES taxes(id),
  amount_untaxed  NUMERIC(15,2) DEFAULT 0,
  amount_tax      NUMERIC(15,2) DEFAULT 0,
  amount_total    NUMERIC(15,2) DEFAULT 0,
  account_id      INTEGER REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS payments (
  id           SERIAL PRIMARY KEY,
  company_id   INTEGER REFERENCES companies(id),
  partner_id   INTEGER REFERENCES partners(id),
  payment_type VARCHAR(50)   NOT NULL,
  amount       NUMERIC(15,2) NOT NULL,
  currency     VARCHAR(3)    DEFAULT 'AED',
  date         DATE          NOT NULL,
  journal_id   INTEGER REFERENCES journals(id),
  ref          VARCHAR(100),
  memo         TEXT,
  state        VARCHAR(50)   DEFAULT 'draft',
  move_id      INTEGER REFERENCES moves(id),
  created_at   TIMESTAMP     DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payment_reconcile (
  id          SERIAL PRIMARY KEY,
  payment_id  INTEGER REFERENCES payments(id),
  move_id     INTEGER REFERENCES moves(id),
  amount      NUMERIC(15,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_modules (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  module      VARCHAR(50) NOT NULL,
  enabled     BOOLEAN DEFAULT TRUE,
  UNIQUE(company_id, module)
);

ALTER TABLE companies ADD COLUMN IF NOT EXISTS status   VARCHAR(20) DEFAULT 'active';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS plan     VARCHAR(50) DEFAULT 'standard';
ALTER TABLE users     ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS asset_categories (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  name        VARCHAR(100) NOT NULL,
  depreciation_method VARCHAR(50) DEFAULT 'straight_line',
  useful_life INTEGER DEFAULT 5,
  account_code VARCHAR(20),
  active      BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS assets (
  id              SERIAL PRIMARY KEY,
  company_id      INTEGER REFERENCES companies(id),
  name            VARCHAR(255) NOT NULL,
  asset_number    VARCHAR(50),
  category_id     INTEGER REFERENCES asset_categories(id),
  state           VARCHAR(50) DEFAULT 'draft',
  purchase_date   DATE,
  in_service_date DATE,
  purchase_value  NUMERIC(15,2) DEFAULT 0,
  salvage_value   NUMERIC(15,2) DEFAULT 0,
  useful_life     INTEGER DEFAULT 5,
  depreciation_method VARCHAR(50) DEFAULT 'straight_line',
  accumulated_depreciation NUMERIC(15,2) DEFAULT 0,
  book_value      NUMERIC(15,2) DEFAULT 0,
  asset_account_id        INTEGER REFERENCES accounts(id),
  depreciation_account_id INTEGER REFERENCES accounts(id),
  expense_account_id      INTEGER REFERENCES accounts(id),
  partner_id      INTEGER REFERENCES partners(id),
  location        VARCHAR(255),
  serial_number   VARCHAR(100),
  notes           TEXT,
  active          BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS asset_depreciation_lines (
  id          SERIAL PRIMARY KEY,
  asset_id    INTEGER REFERENCES assets(id) ON DELETE CASCADE,
  company_id  INTEGER REFERENCES companies(id),
  date        DATE NOT NULL,
  amount      NUMERIC(15,2) NOT NULL,
  book_value_after NUMERIC(15,2) DEFAULT 0,
  move_id     INTEGER REFERENCES moves(id),
  state       VARCHAR(50) DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS crm_leads (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  name        VARCHAR(255) NOT NULL,
  partner_id  INTEGER REFERENCES partners(id),
  contact_name VARCHAR(255),
  email       VARCHAR(255),
  phone       VARCHAR(50),
  stage       VARCHAR(50) DEFAULT 'new',
  priority    INTEGER DEFAULT 0,
  expected_revenue NUMERIC(15,2) DEFAULT 0,
  probability NUMERIC(5,2) DEFAULT 0,
  assigned_user_id INTEGER REFERENCES users(id),
  description TEXT,
  closing_date DATE,
  active      BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hr_employees (
  id              SERIAL PRIMARY KEY,
  company_id      INTEGER REFERENCES companies(id),
  name            VARCHAR(255) NOT NULL,
  employee_number VARCHAR(50),
  job_title       VARCHAR(100),
  department      VARCHAR(100),
  email           VARCHAR(255),
  phone           VARCHAR(50),
  nationality     VARCHAR(100),
  id_number       VARCHAR(50),
  passport_number VARCHAR(50),
  hire_date       DATE,
  contract_type   VARCHAR(50) DEFAULT 'full_time',
  basic_salary    NUMERIC(15,2) DEFAULT 0,
  housing_allowance NUMERIC(15,2) DEFAULT 0,
  transport_allowance NUMERIC(15,2) DEFAULT 0,
  active          BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hr_leaves (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  employee_id INTEGER REFERENCES hr_employees(id),
  leave_type  VARCHAR(50) DEFAULT 'annual',
  date_from   DATE NOT NULL,
  date_to     DATE NOT NULL,
  days        NUMERIC(5,1),
  state       VARCHAR(50) DEFAULT 'draft',
  notes       TEXT,
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  name        VARCHAR(255) NOT NULL,
  partner_id  INTEGER REFERENCES partners(id),
  manager_user_id INTEGER REFERENCES users(id),
  state       VARCHAR(50) DEFAULT 'open',
  date_start  DATE,
  date_end    DATE,
  description TEXT,
  active      BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_tasks (
  id              SERIAL PRIMARY KEY,
  company_id      INTEGER REFERENCES companies(id),
  project_id      INTEGER REFERENCES projects(id),
  name            VARCHAR(255) NOT NULL,
  assigned_user_id INTEGER REFERENCES users(id),
  stage           VARCHAR(50) DEFAULT 'todo',
  priority        INTEGER DEFAULT 0,
  deadline        DATE,
  description     TEXT,
  planned_hours   NUMERIC(8,2) DEFAULT 0,
  effective_hours NUMERIC(8,2) DEFAULT 0,
  active          BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS timesheets (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  project_id  INTEGER REFERENCES projects(id),
  task_id     INTEGER REFERENCES project_tasks(id),
  employee_id INTEGER REFERENCES hr_employees(id),
  date        DATE NOT NULL,
  description VARCHAR(500),
  hours       NUMERIC(8,2) NOT NULL DEFAULT 0,
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS expense_categories (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  name        VARCHAR(100) NOT NULL,
  account_id  INTEGER REFERENCES accounts(id),
  active      BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS expenses (
  id          SERIAL PRIMARY KEY,
  company_id  INTEGER REFERENCES companies(id),
  employee_id INTEGER REFERENCES hr_employees(id),
  category_id INTEGER REFERENCES expense_categories(id),
  name        VARCHAR(255) NOT NULL,
  date        DATE NOT NULL,
  amount      NUMERIC(15,2) NOT NULL DEFAULT 0,
  tax_id      INTEGER REFERENCES taxes(id),
  state       VARCHAR(50) DEFAULT 'draft',
  notes       TEXT,
  created_at  TIMESTAMP DEFAULT NOW()
);
"""

DEFAULT_COA = [
    # Assets
    ("1000", "Current Assets",            "asset",     None),
    ("1001", "Cash and Bank",             "asset",     "1000"),
    ("1002", "Accounts Receivable",       "asset",     "1000"),
    ("1003", "Inventory",                 "asset",     "1000"),
    ("1004", "Prepaid Expenses",          "asset",     "1000"),
    ("1100", "Fixed Assets",              "asset",     None),
    ("1101", "Property & Equipment",      "asset",     "1100"),
    ("1102", "Accumulated Depreciation",  "asset",     "1100"),
    # Liabilities
    ("2000", "Current Liabilities",       "liability", None),
    ("2001", "Accounts Payable",          "liability", "2000"),
    ("2002", "VAT Payable",               "liability", "2000"),
    ("2003", "Salaries Payable",          "liability", "2000"),
    ("2004", "Accrued Expenses",          "liability", "2000"),
    ("2100", "Long-term Liabilities",     "liability", None),
    ("2101", "Long-term Loans",           "liability", "2100"),
    # Equity
    ("3000", "Equity",                    "equity",    None),
    ("3001", "Share Capital",             "equity",    "3000"),
    ("3002", "Retained Earnings",         "equity",    "3000"),
    ("3003", "Current Year Earnings",     "equity",    "3000"),
    # Revenue
    ("4000", "Revenue",                   "revenue",   None),
    ("4001", "Sales Revenue",             "revenue",   "4000"),
    ("4002", "Service Revenue",           "revenue",   "4000"),
    ("4003", "Other Income",              "revenue",   "4000"),
    # Expenses
    ("5000", "Cost of Sales",             "expense",   None),
    ("5001", "Cost of Goods Sold",        "expense",   "5000"),
    ("5002", "Direct Labor",              "expense",   "5000"),
    ("6000", "Operating Expenses",        "expense",   None),
    ("6001", "Salaries & Wages",          "expense",   "6000"),
    ("6002", "Rent Expense",              "expense",   "6000"),
    ("6003", "Utilities",                 "expense",   "6000"),
    ("6004", "Marketing & Advertising",   "expense",   "6000"),
    ("6005", "Travel & Entertainment",    "expense",   "6000"),
    ("6006", "Professional Fees",         "expense",   "6000"),
    ("6007", "Depreciation",              "expense",   "6000"),
    ("6008", "Bank Charges",              "expense",   "6000"),
    ("6009", "Miscellaneous Expenses",    "expense",   "6000"),
]

MODULES = {
    "invoicing":     {"name": "Sales & Invoicing",   "icon": "🧾", "desc": "Customers, quotes, sales invoices, ZATCA QR"},
    "purchasing":    {"name": "Purchasing",           "icon": "📋", "desc": "Vendors, purchase orders, vendor bills"},
    "accounting":    {"name": "Full Accounting",      "icon": "📒", "desc": "Chart of accounts, journals, P&L, balance sheet, VAT"},
    "payments":      {"name": "Payments",             "icon": "💳", "desc": "Payment tracking, bank reconciliation"},
    "inventory":     {"name": "Inventory",            "icon": "📦", "desc": "Products, stock, multi-warehouse"},
    "crm":           {"name": "CRM",                  "icon": "🎯", "desc": "Leads, pipeline, opportunities"},
    "hr":            {"name": "HR & Payroll",         "icon": "👥", "desc": "Employees, leaves, payslips, gratuity"},
    "project":       {"name": "Project Management",   "icon": "📐", "desc": "Projects, tasks, timesheets"},
    "manufacturing": {"name": "Manufacturing",        "icon": "🏭", "desc": "Bills of materials, work orders"},
    "assets":        {"name": "Asset Management",     "icon": "🏗️", "desc": "Fixed assets, depreciation, disposal"},
    "expenses":      {"name": "Expenses",             "icon": "💸", "desc": "Employee expense claims, approvals"},
    "pos":           {"name": "Point of Sale",        "icon": "🛍️", "desc": "Front-of-house POS, loyalty, receipts"},
}
ALL_MODULES = list(MODULES.keys())


def seed_company(conn, company_id: int, enabled_modules: Optional[List[str]] = None):
    """Seed chart of accounts, taxes, journals for a new company."""
    c = dictcur(conn)

    # Map code → id for parent linking
    code_to_id: dict = {}
    for code, name, actype, parent_code in DEFAULT_COA:
        parent_id = code_to_id.get(parent_code) if parent_code else None
        c.execute(
            "INSERT INTO accounts (company_id,code,name,type,parent_id) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (company_id,code) DO NOTHING RETURNING id",
            (company_id, code, name, actype, parent_id)
        )
        row = c.fetchone()
        if row:
            code_to_id[code] = row["id"]
        else:
            c.execute("SELECT id FROM accounts WHERE company_id=%s AND code=%s", (company_id, code))
            code_to_id[code] = c.fetchone()["id"]

    vat_acct = code_to_id.get("2002")
    ar_acct  = code_to_id.get("1002")
    ap_acct  = code_to_id.get("2001")
    bank_acct = code_to_id.get("1001")

    # Taxes
    for name, rate, ttype in [
        ("VAT 5% (Sales)",    5.0, "sale"),
        ("VAT 5% (Purchase)", 5.0, "purchase"),
        ("Zero-rated (0%)",   0.0, "sale"),
    ]:
        c.execute(
            "INSERT INTO taxes (company_id,name,rate,type,account_id) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (company_id, name, rate, ttype, vat_acct)
        )

    # Journals
    journals_data = [
        ("Sales",            "sale",     "INV",  ar_acct),
        ("Purchase",         "purchase", "BILL",  ap_acct),
        ("Bank",             "bank",     "BNK",  bank_acct),
        ("Cash",             "cash",     "CSH",  bank_acct),
        ("General Journal",  "general",  "JNL",  None),
    ]
    for jname, jtype, prefix, dft_acct in journals_data:
        c.execute(
            "INSERT INTO journals (company_id,name,type,sequence_prefix,default_account_id) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (company_id, jname, jtype, prefix, dft_acct)
        )

    # Seed tenant modules (all enabled by default, or restrict to provided list)
    active = set(enabled_modules) if enabled_modules is not None else set(ALL_MODULES)
    for module in ALL_MODULES:
        c.execute(
            "INSERT INTO tenant_modules (company_id, module, enabled) VALUES (%s, %s, %s) "
            "ON CONFLICT (company_id, module) DO NOTHING",
            (company_id, module, module in active)
        )


def next_sequence(conn, journal_id: int, move_date: date) -> str:
    c = dictcur(conn)
    c.execute(
        "UPDATE journals SET sequence_next = sequence_next + 1 WHERE id=%s RETURNING sequence_prefix, sequence_next - 1 AS seq",
        (journal_id,)
    )
    row = c.fetchone()
    return f"{row['sequence_prefix']}/{move_date.year}/{str(row['seq']).zfill(4)}"


def post_move(conn, move_id: int, company_id: int):
    """Post an invoice or bill: assign name, create journal lines, generate ZATCA QR."""
    move = fetchone(conn, "SELECT * FROM moves WHERE id=%s AND company_id=%s", (move_id, company_id))
    if not move:
        raise HTTPException(404, "Move not found")
    if move["state"] != "draft":
        raise HTTPException(400, f"Move is already {move['state']}")

    lines = fetchall(conn, "SELECT * FROM invoice_lines WHERE move_id=%s", (move_id,))
    if not lines:
        raise HTTPException(400, "Cannot post a move with no lines")

    company = fetchone(conn, "SELECT * FROM companies WHERE id=%s", (company_id,))
    move_date = move["date"] if isinstance(move["date"], date) else date.fromisoformat(str(move["date"]))
    name = next_sequence(conn, move["journal_id"], move_date)

    total_untaxed = sum(float(l["amount_untaxed"]) for l in lines)
    total_tax     = sum(float(l["amount_tax"])     for l in lines)
    total         = total_untaxed + total_tax

    is_sale = move["move_type"] in ("out_invoice", "out_refund")
    is_credit = move["move_type"] in ("out_refund", "in_refund")

    # Partner's AR or AP account
    partner_acct_code = "1002" if is_sale else "2001"
    partner_acct = fetchone(conn,
        "SELECT id FROM accounts WHERE company_id=%s AND code=%s",
        (company_id, partner_acct_code))
    if not partner_acct:
        raise HTTPException(500, f"Account {partner_acct_code} not found")

    jlines: list[dict] = []

    # Partner line (AR debit for sales, AP credit for purchases)
    partner_line: dict = {
        "account_id": partner_acct["id"],
        "name":       name,
        "debit":      total if (is_sale and not is_credit) or (not is_sale and is_credit) else 0,
        "credit":     total if (not is_sale and not is_credit) or (is_sale and is_credit) else 0,
        "partner_id": move["partner_id"],
        "tax_id":     None,
    }
    jlines.append(partner_line)

    # Revenue/expense + tax lines
    for line in lines:
        rev_debit  = 0.0
        rev_credit = float(line["amount_untaxed"])
        if not is_sale:
            rev_debit, rev_credit = rev_credit, rev_debit
        if is_credit:
            rev_debit, rev_credit = rev_credit, rev_debit

        jlines.append({
            "account_id": line["account_id"],
            "name":       line["name"],
            "debit":      rev_debit,
            "credit":     rev_credit,
            "partner_id": move["partner_id"],
            "tax_id":     line.get("tax_id"),
        })

        if line["amount_tax"] and float(line["amount_tax"]) > 0 and line.get("tax_id"):
            tax = fetchone(conn, "SELECT * FROM taxes WHERE id=%s", (line["tax_id"],))
            if tax and tax.get("account_id"):
                t_debit  = 0.0
                t_credit = float(line["amount_tax"])
                if not is_sale:
                    t_debit, t_credit = t_credit, t_debit
                if is_credit:
                    t_debit, t_credit = t_credit, t_debit
                jlines.append({
                    "account_id": tax["account_id"],
                    "name":       f"VAT {tax['rate']}%",
                    "debit":      t_debit,
                    "credit":     t_credit,
                    "partner_id": move["partner_id"],
                    "tax_id":     tax["id"],
                })

    c = dictcur(conn)
    for jl in jlines:
        c.execute(
            "INSERT INTO move_lines (move_id,company_id,account_id,partner_id,name,debit,credit,tax_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (move_id, company_id, jl["account_id"], jl.get("partner_id"),
             jl["name"], jl["debit"], jl["credit"], jl.get("tax_id"))
        )

    # ZATCA QR for sales invoices
    zatca = None
    if move["move_type"] == "out_invoice":
        zatca = gen_zatca_qr(
            company["name"],
            company.get("vat_number") or "0000000000000",
            datetime.now().isoformat(),
            total, total_tax
        )

    due_date = move_date + timedelta(days=30)
    c.execute(
        """UPDATE moves SET name=%s, state='posted',
             amount_untaxed=%s, amount_tax=%s, amount_total=%s, amount_residual=%s,
             zatca_qr=%s, due_date=%s, invoice_date=%s, updated_at=NOW()
           WHERE id=%s""",
        (name, total_untaxed, total_tax, total, total, zatca, due_date, move_date, move_id)
    )


# ── Startup ───────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    with get_db() as conn:
        c = dictcur(conn)
        c.execute(SCHEMA)

        # Add Odoo connection columns (idempotent)
        for col, coltype in [
            ("odoo_url",  "VARCHAR(255)"),
            ("odoo_db",   "VARCHAR(255)"),
            ("odoo_user", "VARCHAR(255)"),
            ("odoo_pass", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col} {coltype}")
            except Exception:
                conn.rollback()

        # Backfill tenant_modules for companies created before multi-tenancy was added
        orphans = fetchall(conn, """
            SELECT c.id FROM companies c
            WHERE NOT EXISTS (
                SELECT 1 FROM tenant_modules tm WHERE tm.company_id = c.id
            )
        """)
        for company in orphans:
            for module in ALL_MODULES:
                c.execute(
                    "INSERT INTO tenant_modules (company_id, module, enabled) "
                    "VALUES (%s, %s, TRUE) ON CONFLICT DO NOTHING",
                    (company["id"], module)
                )


# ── Pydantic models ───────────────────────────────────────────
class LoginIn(BaseModel):
    email: str
    password: str

class SuperAdminIn(BaseModel):
    name: str = "Super Admin"
    email: str
    password: str

class SetupIn(BaseModel):
    company_name: str
    admin_email: str
    admin_password: str
    vat_number: Optional[str] = None
    phone: Optional[str] = None

class TenantIn(BaseModel):
    company_name: str
    admin_email: str
    admin_password: str
    vat_number: Optional[str] = None
    phone: Optional[str] = None
    modules: List[str] = ALL_MODULES

class ModuleToggle(BaseModel):
    modules: List[str]

class StatusUpdate(BaseModel):
    status: str = "active"

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    vat_number: Optional[str] = None
    cr_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    currency: Optional[str] = None

class AccountIn(BaseModel):
    code: str
    name: str
    type: str
    parent_id: Optional[int] = None
    reconcile: bool = False

class PartnerIn(BaseModel):
    name: str
    name_ar: Optional[str] = None
    is_customer: bool = False
    is_vendor: bool = False
    vat_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: str = "UAE"
    payment_terms: int = 30

class ProductIn(BaseModel):
    name: str
    code: Optional[str] = None
    type: str = "service"
    sale_price: float = 0
    cost_price: float = 0
    unit: str = "unit"
    income_account_id: Optional[int] = None
    expense_account_id: Optional[int] = None

class InvoiceLineIn(BaseModel):
    product_id: Optional[int] = None
    name: str
    quantity: float = 1
    unit_price: float = 0
    discount: float = 0
    tax_id: Optional[int] = None
    account_id: Optional[int] = None

class InvoiceIn(BaseModel):
    partner_id: int
    journal_id: Optional[int] = None
    date: str
    ref: Optional[str] = None
    narration: Optional[str] = None
    lines: List[InvoiceLineIn] = []

class PaymentIn(BaseModel):
    partner_id: int
    payment_type: str  # inbound, outbound
    amount: float
    date: str
    journal_id: int
    ref: Optional[str] = None
    memo: Optional[str] = None
    invoice_ids: List[int] = []

class JournalEntryLineIn(BaseModel):
    account_id: int
    name: str
    debit: float = 0
    credit: float = 0
    partner_id: Optional[int] = None

class JournalEntryIn(BaseModel):
    journal_id: int
    date: str
    ref: Optional[str] = None
    narration: Optional[str] = None
    lines: List[JournalEntryLineIn] = []


class AssetCategoryIn(BaseModel):
    name: str
    depreciation_method: str = "straight_line"
    useful_life: int = 5
    account_code: Optional[str] = None

class AssetIn(BaseModel):
    name: str
    asset_number: Optional[str] = None
    category_id: Optional[int] = None
    purchase_date: Optional[str] = None
    in_service_date: Optional[str] = None
    purchase_value: float = 0
    salvage_value: float = 0
    useful_life: int = 5
    depreciation_method: str = "straight_line"
    asset_account_id: Optional[int] = None
    depreciation_account_id: Optional[int] = None
    expense_account_id: Optional[int] = None
    partner_id: Optional[int] = None
    location: Optional[str] = None
    serial_number: Optional[str] = None
    notes: Optional[str] = None

class LeadIn(BaseModel):
    name: str
    partner_id: Optional[int] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    stage: str = "new"
    priority: int = 0
    expected_revenue: float = 0
    probability: float = 0
    assigned_user_id: Optional[int] = None
    description: Optional[str] = None
    closing_date: Optional[str] = None

class EmployeeIn(BaseModel):
    name: str
    employee_number: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nationality: Optional[str] = None
    id_number: Optional[str] = None
    passport_number: Optional[str] = None
    hire_date: Optional[str] = None
    contract_type: str = "full_time"
    basic_salary: float = 0
    housing_allowance: float = 0
    transport_allowance: float = 0

class LeaveIn(BaseModel):
    employee_id: int
    leave_type: str = "annual"
    date_from: str
    date_to: str
    days: Optional[float] = None
    notes: Optional[str] = None

class ProjectIn(BaseModel):
    name: str
    partner_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    state: str = "open"
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    description: Optional[str] = None

class TaskIn(BaseModel):
    project_id: int
    name: str
    assigned_user_id: Optional[int] = None
    stage: str = "todo"
    priority: int = 0
    deadline: Optional[str] = None
    description: Optional[str] = None
    planned_hours: float = 0

class TimesheetIn(BaseModel):
    project_id: int
    task_id: Optional[int] = None
    employee_id: Optional[int] = None
    date: str
    description: Optional[str] = None
    hours: float = 0

class ExpenseCategoryIn(BaseModel):
    name: str
    account_id: Optional[int] = None

class ExpenseIn(BaseModel):
    employee_id: Optional[int] = None
    category_id: Optional[int] = None
    name: str
    date: str
    amount: float = 0
    tax_id: Optional[int] = None
    notes: Optional[str] = None

class UserIn(BaseModel):
    name: str
    email: str
    password: str
    role: str = "staff"

class TenantUpdateIn(BaseModel):
    company_name: Optional[str] = None
    vat_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None

class OdooConnectIn(BaseModel):
    odoo_url: str = "http://187.77.128.199:8069"
    odoo_db: str
    odoo_user: str = "admin"
    odoo_pass: str

class OdooPartnerIn(BaseModel):
    name: str
    is_company: bool = True
    is_customer: bool = False
    is_vendor: bool = False
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    vat: Optional[str] = None
    ref: Optional[str] = None

class OdooSaleLineIn(BaseModel):
    product_id: int
    name: Optional[str] = None
    product_uom_qty: float = 1.0
    price_unit: float = 0.0

class OdooSaleIn(BaseModel):
    partner_id: int
    date_order: Optional[str] = None
    validity_date: Optional[str] = None
    note: Optional[str] = None
    order_line: List[OdooSaleLineIn] = []

class OdooInvoiceLineIn(BaseModel):
    product_id: Optional[int] = None
    name: str
    quantity: float = 1.0
    price_unit: float = 0.0
    tax_ids: List[int] = []

class OdooInvoiceIn(BaseModel):
    partner_id: int
    move_type: str = "out_invoice"
    invoice_date: Optional[str] = None
    invoice_date_due: Optional[str] = None
    ref: Optional[str] = None
    narration: Optional[str] = None
    invoice_line_ids: List[OdooInvoiceLineIn] = []

class OdooProductIn(BaseModel):
    name: str
    type: str = "service"
    list_price: float = 0.0
    standard_price: float = 0.0
    default_code: Optional[str] = None
    description: Optional[str] = None
    categ_id: Optional[int] = None

class OdooLeadIn(BaseModel):
    name: str
    partner_name: Optional[str] = None
    contact_name: Optional[str] = None
    email_from: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    expected_revenue: float = 0.0
    type: str = "lead"

class PortalProvisionIn(BaseModel):
    company_name: str
    admin_email: str
    admin_password: str
    industry: Optional[str] = None
    modules: List[str] = []
    team_size: Optional[str] = None
    portal_api_key: str


# ── Setup ─────────────────────────────────────────────────────
@app.get("/api/setup/status")
def setup_status():
    with get_db() as conn:
        companies = fetchone(conn, "SELECT COUNT(*) AS n FROM companies")
        super_row = fetchone(conn, "SELECT COUNT(*) AS n FROM users WHERE is_super_admin=TRUE")
        return {
            "initialized":  companies and int(companies["n"]) > 0,
            "has_super":    super_row  and int(super_row["n"]) > 0,
        }

@app.post("/api/setup/init")
def setup_init(data: SetupIn):
    with get_db() as conn:
        # Block only if a super admin already created tenants (has_super flow)
        super_exists = fetchone(conn, "SELECT id FROM users WHERE is_super_admin=TRUE LIMIT 1")
        if super_exists:
            raise HTTPException(400, "Use super admin panel to create tenants")
        c = dictcur(conn)
        c.execute(
            "INSERT INTO companies (name,vat_number,phone) VALUES (%s,%s,%s) RETURNING id",
            (data.company_name, data.vat_number, data.phone)
        )
        company_id = c.fetchone()["id"]
        seed_company(conn, company_id)
        phash = pwd_ctx.hash(data.admin_password)
        c.execute(
            "INSERT INTO users (name,email,password_hash,role,company_id) VALUES (%s,%s,%s,'admin',%s) RETURNING id",
            ("Admin", data.admin_email, phash, company_id)
        )
        user_id = c.fetchone()["id"]
        token = make_token(user_id, company_id)
        return {"access_token": token, "company_id": company_id}


# ── Auth ──────────────────────────────────────────────────────
@app.post("/api/auth/login")
def login(data: LoginIn):
    with get_db() as conn:
        user = fetchone(conn, "SELECT * FROM users WHERE email=%s AND active=TRUE", (data.email,))
        if not user or not pwd_ctx.verify(data.password, user["password_hash"]):
            raise HTTPException(401, "Invalid credentials")
        is_super = bool(user.get("is_super_admin"))
        token = make_token(user["id"], user.get("company_id"), is_super=is_super)
        return {"access_token": token, "user": {
            "id": user["id"], "name": user["name"],
            "email": user["email"], "role": user["role"],
            "is_super": is_super,
            "company_id": user.get("company_id"),
        }}

@app.get("/api/auth/me")
def me(ctx=Depends(get_user)):
    with get_db() as conn:
        user = fetchone(conn, "SELECT id,name,email,role,company_id,is_super_admin FROM users WHERE id=%s", (ctx["user_id"],))
        if not user:
            raise HTTPException(404, "User not found")
        user["is_super"] = bool(user.pop("is_super_admin", False))
        return user


# ── Company ───────────────────────────────────────────────────
@app.get("/api/company")
def get_company(ctx=Depends(get_user)):
    with get_db() as conn:
        return fetchone(conn, "SELECT * FROM companies WHERE id=%s", (ctx["company_id"],))

@app.put("/api/company")
def update_company(data: CompanyUpdate, ctx=Depends(get_user)):
    with get_db() as conn:
        updates = {k: v for k, v in data.dict().items() if v is not None}
        if not updates:
            return fetchone(conn, "SELECT * FROM companies WHERE id=%s", (ctx["company_id"],))
        set_clause = ", ".join(f"{k}=%s" for k in updates)
        vals = list(updates.values()) + [ctx["company_id"]]
        execute(conn, f"UPDATE companies SET {set_clause} WHERE id=%s", vals)
        return fetchone(conn, "SELECT * FROM companies WHERE id=%s", (ctx["company_id"],))


# ── Chart of Accounts ─────────────────────────────────────────
@app.get("/api/accounts")
def list_accounts(type: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = "SELECT * FROM accounts WHERE company_id=%s AND active=TRUE"
        params: list = [ctx["company_id"]]
        if type:
            sql += " AND type=%s"
            params.append(type)
        sql += " ORDER BY code"
        return fetchall(conn, sql, params)

@app.post("/api/accounts")
def create_account(data: AccountIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "INSERT INTO accounts (company_id,code,name,type,parent_id,reconcile) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.code, data.name, data.type, data.parent_id, data.reconcile))

@app.put("/api/accounts/{aid}")
def update_account(aid: int, data: AccountIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "UPDATE accounts SET code=%s,name=%s,type=%s,parent_id=%s,reconcile=%s WHERE id=%s AND company_id=%s RETURNING *",
            (data.code, data.name, data.type, data.parent_id, data.reconcile, aid, ctx["company_id"]))

@app.delete("/api/accounts/{aid}")
def delete_account(aid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE accounts SET active=FALSE WHERE id=%s AND company_id=%s", (aid, ctx["company_id"]))
        return {"ok": True}


# ── Partners ──────────────────────────────────────────────────
@app.get("/api/partners")
def list_partners(is_customer: Optional[bool] = None, is_vendor: Optional[bool] = None,
                  search: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = "SELECT * FROM partners WHERE company_id=%s AND active=TRUE"
        params: list = [ctx["company_id"]]
        if is_customer is not None:
            sql += " AND is_customer=%s"; params.append(is_customer)
        if is_vendor is not None:
            sql += " AND is_vendor=%s"; params.append(is_vendor)
        if search:
            sql += " AND (name ILIKE %s OR email ILIKE %s)"; params += [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY name"
        return fetchall(conn, sql, params)

@app.post("/api/partners")
def create_partner(data: PartnerIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "INSERT INTO partners (company_id,name,name_ar,is_customer,is_vendor,vat_number,email,phone,address,city,country,payment_terms) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.name, data.name_ar, data.is_customer, data.is_vendor,
             data.vat_number, data.email, data.phone, data.address, data.city, data.country, data.payment_terms))

@app.get("/api/partners/{pid}")
def get_partner(pid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        p = fetchone(conn, "SELECT * FROM partners WHERE id=%s AND company_id=%s", (pid, ctx["company_id"]))
        if not p:
            raise HTTPException(404)
        return p

@app.put("/api/partners/{pid}")
def update_partner(pid: int, data: PartnerIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "UPDATE partners SET name=%s,name_ar=%s,is_customer=%s,is_vendor=%s,vat_number=%s,"
            "email=%s,phone=%s,address=%s,city=%s,country=%s,payment_terms=%s WHERE id=%s AND company_id=%s RETURNING *",
            (data.name, data.name_ar, data.is_customer, data.is_vendor, data.vat_number,
             data.email, data.phone, data.address, data.city, data.country, data.payment_terms, pid, ctx["company_id"]))

@app.delete("/api/partners/{pid}")
def delete_partner(pid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE partners SET active=FALSE WHERE id=%s AND company_id=%s", (pid, ctx["company_id"]))
        return {"ok": True}


# ── Products ──────────────────────────────────────────────────
@app.get("/api/products")
def list_products(search: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = "SELECT p.*, ia.code AS income_account_code, ea.code AS expense_account_code FROM products p " \
              "LEFT JOIN accounts ia ON ia.id=p.income_account_id " \
              "LEFT JOIN accounts ea ON ea.id=p.expense_account_id " \
              "WHERE p.company_id=%s AND p.active=TRUE"
        params: list = [ctx["company_id"]]
        if search:
            sql += " AND (p.name ILIKE %s OR p.code ILIKE %s)"; params += [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY p.name"
        return fetchall(conn, sql, params)

@app.post("/api/products")
def create_product(data: ProductIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "INSERT INTO products (company_id,name,code,type,sale_price,cost_price,unit,income_account_id,expense_account_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.name, data.code, data.type, data.sale_price,
             data.cost_price, data.unit, data.income_account_id, data.expense_account_id))

@app.get("/api/products/{pid}")
def get_product(pid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        p = fetchone(conn, "SELECT * FROM products WHERE id=%s AND company_id=%s", (pid, ctx["company_id"]))
        if not p: raise HTTPException(404)
        return p

@app.put("/api/products/{pid}")
def update_product(pid: int, data: ProductIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "UPDATE products SET name=%s,code=%s,type=%s,sale_price=%s,cost_price=%s,unit=%s,"
            "income_account_id=%s,expense_account_id=%s WHERE id=%s AND company_id=%s RETURNING *",
            (data.name, data.code, data.type, data.sale_price, data.cost_price, data.unit,
             data.income_account_id, data.expense_account_id, pid, ctx["company_id"]))

@app.delete("/api/products/{pid}")
def delete_product(pid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE products SET active=FALSE WHERE id=%s AND company_id=%s", (pid, ctx["company_id"]))
        return {"ok": True}


# ── Taxes ─────────────────────────────────────────────────────
@app.get("/api/taxes")
def list_taxes(type: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = "SELECT * FROM taxes WHERE company_id=%s AND active=TRUE"
        params: list = [ctx["company_id"]]
        if type:
            sql += " AND type=%s"; params.append(type)
        sql += " ORDER BY type, rate"
        return fetchall(conn, sql, params)


# ── Journals ──────────────────────────────────────────────────
@app.get("/api/journals")
def list_journals(type: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = "SELECT * FROM journals WHERE company_id=%s AND active=TRUE"
        params: list = [ctx["company_id"]]
        if type:
            sql += " AND type=%s"; params.append(type)
        sql += " ORDER BY name"
        return fetchall(conn, sql, params)


# ── Invoices ──────────────────────────────────────────────────
def _calc_line(line: InvoiceLineIn, conn, company_id: int) -> dict:
    """Compute amounts for one invoice line."""
    qty    = line.quantity
    price  = line.unit_price
    disc   = line.discount or 0
    untaxed = round(qty * price * (1 - disc / 100), 2)

    tax_amount = 0.0
    if line.tax_id:
        tax = fetchone(conn, "SELECT rate FROM taxes WHERE id=%s AND company_id=%s", (line.tax_id, company_id))
        if tax:
            tax_amount = round(untaxed * float(tax["rate"]) / 100, 2)

    # Resolve account
    acct_id = line.account_id
    if not acct_id and line.product_id:
        prod = fetchone(conn, "SELECT income_account_id FROM products WHERE id=%s", (line.product_id,))
        if prod:
            acct_id = prod.get("income_account_id")
    if not acct_id:
        acct = fetchone(conn, "SELECT id FROM accounts WHERE company_id=%s AND code='4001'", (company_id,))
        if acct:
            acct_id = acct["id"]

    return {
        "product_id":    line.product_id,
        "name":          line.name,
        "quantity":      qty,
        "unit_price":    price,
        "discount":      disc,
        "tax_id":        line.tax_id,
        "amount_untaxed": untaxed,
        "amount_tax":    tax_amount,
        "amount_total":  untaxed + tax_amount,
        "account_id":    acct_id,
    }

def _get_default_journal(conn, company_id: int, jtype: str) -> Optional[int]:
    j = fetchone(conn, "SELECT id FROM journals WHERE company_id=%s AND type=%s AND active=TRUE LIMIT 1",
                 (company_id, jtype))
    return j["id"] if j else None

def _create_move(conn, data: InvoiceIn, move_type: str, company_id: int, user_id: int) -> dict:
    journal_id = data.journal_id or _get_default_journal(conn, company_id,
                                                          "sale" if "out" in move_type else "purchase")
    if not journal_id:
        raise HTTPException(400, "No journal found")

    move_date = date.fromisoformat(data.date)
    c = dictcur(conn)
    c.execute(
        "INSERT INTO moves (company_id,move_type,date,partner_id,journal_id,ref,narration,created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (company_id, move_type, move_date, data.partner_id, journal_id,
         data.ref, data.narration, user_id)
    )
    move = dict(c.fetchone())
    move_id = move["id"]

    for line in data.lines:
        ld = _calc_line(line, conn, company_id)
        c.execute(
            "INSERT INTO invoice_lines (move_id,product_id,name,quantity,unit_price,discount,tax_id,"
            "amount_untaxed,amount_tax,amount_total,account_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (move_id, ld["product_id"], ld["name"], ld["quantity"], ld["unit_price"], ld["discount"],
             ld["tax_id"], ld["amount_untaxed"], ld["amount_tax"], ld["amount_total"], ld["account_id"])
        )

    move["lines"] = fetchall(conn, "SELECT * FROM invoice_lines WHERE move_id=%s", (move_id,))
    return move

def _list_moves(conn, move_type_like: str, company_id: int,
                state: Optional[str], partner_id: Optional[int],
                date_from: Optional[str], date_to: Optional[str]) -> list:
    sql = """SELECT m.*, p.name AS partner_name
             FROM moves m LEFT JOIN partners p ON p.id=m.partner_id
             WHERE m.company_id=%s AND m.move_type LIKE %s"""
    params: list = [company_id, move_type_like]
    if state:
        sql += " AND m.state=%s"; params.append(state)
    if partner_id:
        sql += " AND m.partner_id=%s"; params.append(partner_id)
    if date_from:
        sql += " AND m.date >= %s"; params.append(date_from)
    if date_to:
        sql += " AND m.date <= %s"; params.append(date_to)
    sql += " ORDER BY m.date DESC, m.id DESC"
    return fetchall(conn, sql, params)

def _get_move(conn, move_id: int, move_type_like: str, company_id: int) -> dict:
    move = fetchone(conn,
        """SELECT m.*, p.name AS partner_name, j.name AS journal_name
           FROM moves m
           LEFT JOIN partners p ON p.id=m.partner_id
           LEFT JOIN journals j ON j.id=m.journal_id
           WHERE m.id=%s AND m.company_id=%s AND m.move_type LIKE %s""",
        (move_id, company_id, move_type_like))
    if not move:
        raise HTTPException(404)
    move["lines"] = fetchall(conn, "SELECT * FROM invoice_lines WHERE move_id=%s ORDER BY id", (move_id,))
    return move


# Invoices (out_invoice)
@app.get("/api/invoices")
def list_invoices(state: Optional[str] = None, partner_id: Optional[int] = None,
                  date_from: Optional[str] = None, date_to: Optional[str] = None,
                  ctx=Depends(get_user)):
    with get_db() as conn:
        return _list_moves(conn, "out_%", ctx["company_id"], state, partner_id, date_from, date_to)

@app.post("/api/invoices")
def create_invoice(data: InvoiceIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return _create_move(conn, data, "out_invoice", ctx["company_id"], ctx["user_id"])

@app.get("/api/invoices/{mid}")
def get_invoice(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        return _get_move(conn, mid, "out_%", ctx["company_id"])

@app.put("/api/invoices/{mid}")
def update_invoice(mid: int, data: InvoiceIn, ctx=Depends(get_user)):
    with get_db() as conn:
        move = fetchone(conn, "SELECT state FROM moves WHERE id=%s AND company_id=%s", (mid, ctx["company_id"]))
        if not move or move["state"] != "draft":
            raise HTTPException(400, "Only draft invoices can be edited")
        c = dictcur(conn)
        c.execute("DELETE FROM invoice_lines WHERE move_id=%s", (mid,))
        move_date = date.fromisoformat(data.date)
        c.execute(
            "UPDATE moves SET partner_id=%s,date=%s,ref=%s,narration=%s,updated_at=NOW() WHERE id=%s",
            (data.partner_id, move_date, data.ref, data.narration, mid)
        )
        for line in data.lines:
            ld = _calc_line(line, conn, ctx["company_id"])
            c.execute(
                "INSERT INTO invoice_lines (move_id,product_id,name,quantity,unit_price,discount,tax_id,"
                "amount_untaxed,amount_tax,amount_total,account_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (mid, ld["product_id"], ld["name"], ld["quantity"], ld["unit_price"], ld["discount"],
                 ld["tax_id"], ld["amount_untaxed"], ld["amount_tax"], ld["amount_total"], ld["account_id"])
            )
        return _get_move(conn, mid, "out_%", ctx["company_id"])

@app.post("/api/invoices/{mid}/confirm")
def confirm_invoice(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        post_move(conn, mid, ctx["company_id"])
        return _get_move(conn, mid, "out_%", ctx["company_id"])

@app.post("/api/invoices/{mid}/cancel")
def cancel_invoice(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn,
            "UPDATE moves SET state='cancelled',updated_at=NOW() WHERE id=%s AND company_id=%s AND move_type LIKE 'out_%'",
            (mid, ctx["company_id"]))
        execute(conn, "DELETE FROM move_lines WHERE move_id=%s", (mid,))
        return _get_move(conn, mid, "out_%", ctx["company_id"])

@app.delete("/api/invoices/{mid}")
def delete_invoice(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        move = fetchone(conn, "SELECT state FROM moves WHERE id=%s AND company_id=%s", (mid, ctx["company_id"]))
        if not move or move["state"] != "draft":
            raise HTTPException(400, "Only draft invoices can be deleted")
        execute(conn, "DELETE FROM moves WHERE id=%s AND company_id=%s", (mid, ctx["company_id"]))
        return {"ok": True}


# Bills (in_invoice)
@app.get("/api/bills")
def list_bills(state: Optional[str] = None, partner_id: Optional[int] = None,
               date_from: Optional[str] = None, date_to: Optional[str] = None,
               ctx=Depends(get_user)):
    with get_db() as conn:
        return _list_moves(conn, "in_%", ctx["company_id"], state, partner_id, date_from, date_to)

@app.post("/api/bills")
def create_bill(data: InvoiceIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return _create_move(conn, data, "in_invoice", ctx["company_id"], ctx["user_id"])

@app.get("/api/bills/{mid}")
def get_bill(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        return _get_move(conn, mid, "in_%", ctx["company_id"])

@app.put("/api/bills/{mid}")
def update_bill(mid: int, data: InvoiceIn, ctx=Depends(get_user)):
    with get_db() as conn:
        move = fetchone(conn, "SELECT state FROM moves WHERE id=%s AND company_id=%s", (mid, ctx["company_id"]))
        if not move or move["state"] != "draft":
            raise HTTPException(400, "Only draft bills can be edited")
        c = dictcur(conn)
        c.execute("DELETE FROM invoice_lines WHERE move_id=%s", (mid,))
        move_date = date.fromisoformat(data.date)
        c.execute("UPDATE moves SET partner_id=%s,date=%s,ref=%s,narration=%s,updated_at=NOW() WHERE id=%s",
                  (data.partner_id, move_date, data.ref, data.narration, mid))
        for line in data.lines:
            ld = _calc_line(line, conn, ctx["company_id"])
            # For bills, use expense account instead of income
            if not ld["account_id"] and line.product_id:
                prod = fetchone(conn, "SELECT expense_account_id FROM products WHERE id=%s", (line.product_id,))
                if prod:
                    ld["account_id"] = prod.get("expense_account_id")
            if not ld["account_id"]:
                acct = fetchone(conn, "SELECT id FROM accounts WHERE company_id=%s AND code='5001'", (ctx["company_id"],))
                if acct:
                    ld["account_id"] = acct["id"]
            c.execute(
                "INSERT INTO invoice_lines (move_id,product_id,name,quantity,unit_price,discount,tax_id,"
                "amount_untaxed,amount_tax,amount_total,account_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (mid, ld["product_id"], ld["name"], ld["quantity"], ld["unit_price"], ld["discount"],
                 ld["tax_id"], ld["amount_untaxed"], ld["amount_tax"], ld["amount_total"], ld["account_id"])
            )
        return _get_move(conn, mid, "in_%", ctx["company_id"])

@app.post("/api/bills/{mid}/confirm")
def confirm_bill(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        post_move(conn, mid, ctx["company_id"])
        return _get_move(conn, mid, "in_%", ctx["company_id"])

@app.post("/api/bills/{mid}/cancel")
def cancel_bill(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn,
            "UPDATE moves SET state='cancelled',updated_at=NOW() WHERE id=%s AND company_id=%s AND move_type LIKE 'in_%'",
            (mid, ctx["company_id"]))
        execute(conn, "DELETE FROM move_lines WHERE move_id=%s", (mid,))
        return _get_move(conn, mid, "in_%", ctx["company_id"])

@app.delete("/api/bills/{mid}")
def delete_bill(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        move = fetchone(conn, "SELECT state FROM moves WHERE id=%s AND company_id=%s", (mid, ctx["company_id"]))
        if not move or move["state"] != "draft":
            raise HTTPException(400, "Only draft bills can be deleted")
        execute(conn, "DELETE FROM moves WHERE id=%s AND company_id=%s", (mid, ctx["company_id"]))
        return {"ok": True}


# ── Payments ──────────────────────────────────────────────────
@app.get("/api/payments")
def list_payments(ctx=Depends(get_user)):
    with get_db() as conn:
        return fetchall(conn,
            "SELECT py.*, p.name AS partner_name, j.name AS journal_name "
            "FROM payments py "
            "LEFT JOIN partners p ON p.id=py.partner_id "
            "LEFT JOIN journals j ON j.id=py.journal_id "
            "WHERE py.company_id=%s ORDER BY py.date DESC, py.id DESC",
            (ctx["company_id"],))

@app.post("/api/payments")
def create_payment(data: PaymentIn, ctx=Depends(get_user)):
    with get_db() as conn:
        pay_date = date.fromisoformat(data.date)
        c = dictcur(conn)
        c.execute(
            "INSERT INTO payments (company_id,partner_id,payment_type,amount,date,journal_id,ref,memo) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.partner_id, data.payment_type, data.amount,
             pay_date, data.journal_id, data.ref, data.memo)
        )
        payment = dict(c.fetchone())
        return payment

@app.post("/api/payments/{pid}/post")
def post_payment(pid: int, data: dict = {}, ctx=Depends(get_user)):
    with get_db() as conn:
        payment = fetchone(conn, "SELECT * FROM payments WHERE id=%s AND company_id=%s", (pid, ctx["company_id"]))
        if not payment or payment["state"] != "draft":
            raise HTTPException(400, "Payment not found or already posted")

        pay_date = payment["date"] if isinstance(payment["date"], date) else date.fromisoformat(str(payment["date"]))

        # Determine accounts
        journal = fetchone(conn, "SELECT * FROM journals WHERE id=%s", (payment["journal_id"],))
        bank_acct = journal.get("default_account_id") if journal else None

        if payment["payment_type"] == "inbound":
            # Customer payment: debit bank, credit AR
            ar_acct = fetchone(conn, "SELECT id FROM accounts WHERE company_id=%s AND code='1002'", (ctx["company_id"],))
            debit_acct  = bank_acct
            credit_acct = ar_acct["id"] if ar_acct else None
        else:
            # Vendor payment: debit AP, credit bank
            ap_acct = fetchone(conn, "SELECT id FROM accounts WHERE company_id=%s AND code='2001'", (ctx["company_id"],))
            debit_acct  = ap_acct["id"] if ap_acct else None
            credit_acct = bank_acct

        # Get default general journal for payment
        gen_journal = fetchone(conn,
            "SELECT id FROM journals WHERE company_id=%s AND type IN ('bank','cash') LIMIT 1",
            (ctx["company_id"],))
        journal_id = payment["journal_id"] or (gen_journal["id"] if gen_journal else None)

        name = next_sequence(conn, journal_id, pay_date)

        c = dictcur(conn)
        c.execute(
            "INSERT INTO moves (company_id,name,move_type,state,date,partner_id,journal_id,amount_total,amount_residual,currency,created_by) "
            "VALUES (%s,%s,'entry','posted',%s,%s,%s,%s,0,%s,%s) RETURNING id",
            (ctx["company_id"], name, pay_date, payment["partner_id"], journal_id,
             float(payment["amount"]), "AED", ctx["user_id"])
        )
        move_id = c.fetchone()["id"]

        amount = float(payment["amount"])
        for acct_id, debit, credit in [
            (debit_acct, amount, 0),
            (credit_acct, 0, amount),
        ]:
            if acct_id:
                c.execute(
                    "INSERT INTO move_lines (move_id,company_id,account_id,partner_id,name,debit,credit) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (move_id, ctx["company_id"], acct_id, payment["partner_id"],
                     f"Payment: {name}", debit, credit)
                )

        c.execute("UPDATE payments SET state='posted', move_id=%s WHERE id=%s", (move_id, pid))
        return fetchone(conn, "SELECT * FROM payments WHERE id=%s", (pid,))


# ── Journal Entries ───────────────────────────────────────────
@app.get("/api/journal-entries")
def list_journal_entries(ctx=Depends(get_user)):
    with get_db() as conn:
        return fetchall(conn,
            "SELECT m.*, j.name AS journal_name FROM moves m "
            "LEFT JOIN journals j ON j.id=m.journal_id "
            "WHERE m.company_id=%s AND m.move_type='entry' ORDER BY m.date DESC, m.id DESC",
            (ctx["company_id"],))

@app.post("/api/journal-entries")
def create_journal_entry(data: JournalEntryIn, ctx=Depends(get_user)):
    with get_db() as conn:
        entry_date = date.fromisoformat(data.date)
        total_debit  = sum(l.debit  for l in data.lines)
        total_credit = sum(l.credit for l in data.lines)
        if abs(total_debit - total_credit) > 0.01:
            raise HTTPException(400, f"Entry not balanced: debit={total_debit:.2f} credit={total_credit:.2f}")

        c = dictcur(conn)
        c.execute(
            "INSERT INTO moves (company_id,move_type,state,date,journal_id,ref,narration,created_by) "
            "VALUES (%s,'entry','draft',%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], entry_date, data.journal_id, data.ref, data.narration, ctx["user_id"])
        )
        move = dict(c.fetchone())
        move_id = move["id"]

        for line in data.lines:
            c.execute(
                "INSERT INTO move_lines (move_id,company_id,account_id,partner_id,name,debit,credit) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (move_id, ctx["company_id"], line.account_id, line.partner_id,
                 line.name, line.debit, line.credit)
            )
        move["lines"] = data.lines
        return move

@app.post("/api/journal-entries/{mid}/post")
def post_journal_entry(mid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        move = fetchone(conn, "SELECT * FROM moves WHERE id=%s AND company_id=%s AND move_type='entry'",
                        (mid, ctx["company_id"]))
        if not move or move["state"] != "draft":
            raise HTTPException(400, "Entry not found or already posted")
        entry_date = move["date"] if isinstance(move["date"], date) else date.fromisoformat(str(move["date"]))
        name = next_sequence(conn, move["journal_id"], entry_date)
        execute(conn, "UPDATE moves SET name=%s,state='posted',updated_at=NOW() WHERE id=%s", (name, mid))
        return fetchone(conn, "SELECT * FROM moves WHERE id=%s", (mid,))


# ── Reports ───────────────────────────────────────────────────
@app.get("/api/reports/trial-balance")
def trial_balance(date_from: Optional[str] = None, date_to: Optional[str] = None,
                  ctx=Depends(get_user)):
    with get_db() as conn:
        sql = """
            SELECT a.code, a.name, a.type,
                   COALESCE(SUM(ml.debit), 0)  AS total_debit,
                   COALESCE(SUM(ml.credit), 0) AS total_credit,
                   COALESCE(SUM(ml.debit - ml.credit), 0) AS balance
            FROM accounts a
            LEFT JOIN move_lines ml ON ml.account_id = a.id
            LEFT JOIN moves m ON m.id = ml.move_id AND m.state = 'posted'
            WHERE a.company_id = %s AND a.active = TRUE
        """
        params: list = [ctx["company_id"]]
        if date_from:
            sql += " AND (m.date IS NULL OR m.date >= %s)"; params.append(date_from)
        if date_to:
            sql += " AND (m.date IS NULL OR m.date <= %s)"; params.append(date_to)
        sql += " GROUP BY a.id, a.code, a.name, a.type ORDER BY a.code"
        rows = fetchall(conn, sql, params)
        total_debit  = sum(float(r["total_debit"])  for r in rows)
        total_credit = sum(float(r["total_credit"]) for r in rows)
        return {"lines": rows, "total_debit": total_debit, "total_credit": total_credit,
                "balanced": abs(total_debit - total_credit) < 0.01}

@app.get("/api/reports/profit-loss")
def profit_loss(date_from: Optional[str] = None, date_to: Optional[str] = None,
                ctx=Depends(get_user)):
    with get_db() as conn:
        sql = """
            SELECT a.code, a.name, a.type,
                   COALESCE(SUM(ml.credit - ml.debit), 0) AS amount
            FROM accounts a
            LEFT JOIN move_lines ml ON ml.account_id = a.id
            LEFT JOIN moves m ON m.id = ml.move_id AND m.state = 'posted'
            WHERE a.company_id = %s AND a.type IN ('revenue', 'expense') AND a.active = TRUE
        """
        params: list = [ctx["company_id"]]
        if date_from:
            sql += " AND (m.date IS NULL OR m.date >= %s)"; params.append(date_from)
        if date_to:
            sql += " AND (m.date IS NULL OR m.date <= %s)"; params.append(date_to)
        sql += " GROUP BY a.id, a.code, a.name, a.type ORDER BY a.type DESC, a.code"
        rows = fetchall(conn, sql, params)
        revenue  = sum(float(r["amount"]) for r in rows if r["type"] == "revenue")
        expense  = sum(float(r["amount"]) for r in rows if r["type"] == "expense")
        return {"lines": rows, "total_revenue": revenue, "total_expense": expense,
                "net_profit": revenue - expense}

@app.get("/api/reports/balance-sheet")
def balance_sheet(as_of: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = """
            SELECT a.code, a.name, a.type,
                   COALESCE(SUM(ml.debit - ml.credit), 0) AS balance
            FROM accounts a
            LEFT JOIN move_lines ml ON ml.account_id = a.id
            LEFT JOIN moves m ON m.id = ml.move_id AND m.state = 'posted'
            WHERE a.company_id = %s AND a.type IN ('asset','liability','equity') AND a.active = TRUE
        """
        params: list = [ctx["company_id"]]
        if as_of:
            sql += " AND (m.date IS NULL OR m.date <= %s)"; params.append(as_of)
        sql += " GROUP BY a.id, a.code, a.name, a.type ORDER BY a.type, a.code"
        rows = fetchall(conn, sql, params)
        assets      = sum(float(r["balance"]) for r in rows if r["type"] == "asset")
        liabilities = sum(float(r["balance"]) for r in rows if r["type"] == "liability")
        equity      = sum(float(r["balance"]) for r in rows if r["type"] == "equity")
        return {"lines": rows, "total_assets": assets,
                "total_liabilities": liabilities, "total_equity": equity}

@app.get("/api/reports/vat-return")
def vat_return(date_from: str, date_to: str, ctx=Depends(get_user)):
    with get_db() as conn:
        # Output VAT (on sales invoices)
        out_rows = fetchall(conn, """
            SELECT COALESCE(SUM(il.amount_untaxed), 0) AS taxable,
                   COALESCE(SUM(il.amount_tax), 0) AS vat
            FROM invoice_lines il
            JOIN moves m ON m.id = il.move_id
            WHERE m.company_id=%s AND m.move_type='out_invoice' AND m.state='posted'
              AND m.date >= %s AND m.date <= %s AND il.tax_id IS NOT NULL
        """, (ctx["company_id"], date_from, date_to))

        # Input VAT (on vendor bills)
        in_rows = fetchall(conn, """
            SELECT COALESCE(SUM(il.amount_untaxed), 0) AS taxable,
                   COALESCE(SUM(il.amount_tax), 0) AS vat
            FROM invoice_lines il
            JOIN moves m ON m.id = il.move_id
            WHERE m.company_id=%s AND m.move_type='in_invoice' AND m.state='posted'
              AND m.date >= %s AND m.date <= %s AND il.tax_id IS NOT NULL
        """, (ctx["company_id"], date_from, date_to))

        output_taxable = float(out_rows[0]["taxable"]) if out_rows else 0
        output_vat     = float(out_rows[0]["vat"])     if out_rows else 0
        input_taxable  = float(in_rows[0]["taxable"])  if in_rows  else 0
        input_vat      = float(in_rows[0]["vat"])      if in_rows  else 0

        return {
            "date_from":       date_from,
            "date_to":         date_to,
            "output_taxable":  output_taxable,
            "output_vat":      output_vat,
            "input_taxable":   input_taxable,
            "input_vat":       input_vat,
            "net_vat_payable": output_vat - input_vat,
        }


# ── Dashboard ─────────────────────────────────────────────────
@app.get("/api/dashboard")
def dashboard(ctx=Depends(get_user)):
    with get_db() as conn:
        cid = ctx["company_id"]
        today = date.today()
        month_start = today.replace(day=1)

        def scalar(sql, params=()):
            row = fetchone(conn, sql, params)
            if not row:
                return 0
            v = list(row.values())[0]
            return float(v) if v else 0

        revenue_mtd = scalar(
            "SELECT COALESCE(SUM(amount_untaxed),0) FROM moves "
            "WHERE company_id=%s AND move_type='out_invoice' AND state='posted' AND date>=%s",
            (cid, month_start))
        expenses_mtd = scalar(
            "SELECT COALESCE(SUM(amount_untaxed),0) FROM moves "
            "WHERE company_id=%s AND move_type='in_invoice' AND state='posted' AND date>=%s",
            (cid, month_start))
        outstanding_invoices = scalar(
            "SELECT COALESCE(SUM(amount_residual),0) FROM moves "
            "WHERE company_id=%s AND move_type='out_invoice' AND state='posted' AND payment_state!='paid'",
            (cid,))
        outstanding_bills = scalar(
            "SELECT COALESCE(SUM(amount_residual),0) FROM moves "
            "WHERE company_id=%s AND move_type='in_invoice' AND state='posted' AND payment_state!='paid'",
            (cid,))
        overdue_invoices = scalar(
            "SELECT COALESCE(SUM(amount_residual),0) FROM moves "
            "WHERE company_id=%s AND move_type='out_invoice' AND state='posted' AND payment_state!='paid' AND due_date<%s",
            (cid, today))

        recent_invoices = fetchall(conn,
            "SELECT m.id, m.name, m.date, m.amount_total, m.state, m.payment_state, p.name AS partner_name "
            "FROM moves m LEFT JOIN partners p ON p.id=m.partner_id "
            "WHERE m.company_id=%s AND m.move_type='out_invoice' "
            "ORDER BY m.date DESC, m.id DESC LIMIT 5", (cid,))

        invoice_count = scalar(
            "SELECT COUNT(*) FROM moves WHERE company_id=%s AND move_type='out_invoice' AND state='posted'", (cid,))
        partner_count = scalar(
            "SELECT COUNT(*) FROM partners WHERE company_id=%s AND active=TRUE", (cid,))

        return {
            "revenue_mtd":         revenue_mtd,
            "expenses_mtd":        expenses_mtd,
            "outstanding_invoices": outstanding_invoices,
            "outstanding_bills":   outstanding_bills,
            "overdue_invoices":    overdue_invoices,
            "invoice_count":       int(invoice_count),
            "partner_count":       int(partner_count),
            "recent_invoices":     recent_invoices,
        }


# ── Asset Management ──────────────────────────────────────────
@app.get("/api/asset-categories")
def list_asset_categories(ctx=Depends(get_user)):
    with get_db() as conn:
        return fetchall(conn, "SELECT * FROM asset_categories WHERE company_id=%s AND active=TRUE ORDER BY name", (ctx["company_id"],))

@app.post("/api/asset-categories")
def create_asset_category(data: AssetCategoryIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "INSERT INTO asset_categories (company_id,name,depreciation_method,useful_life,account_code) VALUES (%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.name, data.depreciation_method, data.useful_life, data.account_code))

@app.put("/api/asset-categories/{cid}")
def update_asset_category(cid: int, data: AssetCategoryIn, ctx=Depends(get_user)):
    with get_db() as conn:
        return execute(conn,
            "UPDATE asset_categories SET name=%s,depreciation_method=%s,useful_life=%s,account_code=%s WHERE id=%s AND company_id=%s RETURNING *",
            (data.name, data.depreciation_method, data.useful_life, data.account_code, cid, ctx["company_id"]))

@app.delete("/api/asset-categories/{cid}")
def delete_asset_category(cid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE asset_categories SET active=FALSE WHERE id=%s AND company_id=%s", (cid, ctx["company_id"]))
        return {"ok": True}

@app.get("/api/assets")
def list_assets(state: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = ("SELECT a.*, ac.name AS category_name, p.name AS vendor_name "
               "FROM assets a "
               "LEFT JOIN asset_categories ac ON ac.id=a.category_id "
               "LEFT JOIN partners p ON p.id=a.partner_id "
               "WHERE a.company_id=%s AND a.active=TRUE")
        params: list = [ctx["company_id"]]
        if state:
            sql += " AND a.state=%s"; params.append(state)
        sql += " ORDER BY a.name"
        return fetchall(conn, sql, params)

@app.post("/api/assets")
def create_asset(data: AssetIn, ctx=Depends(get_user)):
    with get_db() as conn:
        c = dictcur(conn)
        purchase_date = date.fromisoformat(data.purchase_date) if data.purchase_date else None
        in_service_date = date.fromisoformat(data.in_service_date) if data.in_service_date else None
        book_value = data.purchase_value
        c.execute(
            "INSERT INTO assets (company_id,name,asset_number,category_id,purchase_date,in_service_date,"
            "purchase_value,salvage_value,useful_life,depreciation_method,book_value,"
            "asset_account_id,depreciation_account_id,expense_account_id,"
            "partner_id,location,serial_number,notes) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.name, data.asset_number, data.category_id,
             purchase_date, in_service_date, data.purchase_value, data.salvage_value,
             data.useful_life, data.depreciation_method, book_value,
             data.asset_account_id, data.depreciation_account_id, data.expense_account_id,
             data.partner_id, data.location, data.serial_number, data.notes))
        return dict(c.fetchone())

@app.get("/api/assets/{aid}")
def get_asset(aid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        a = fetchone(conn,
            "SELECT a.*, ac.name AS category_name FROM assets a "
            "LEFT JOIN asset_categories ac ON ac.id=a.category_id "
            "WHERE a.id=%s AND a.company_id=%s", (aid, ctx["company_id"]))
        if not a: raise HTTPException(404)
        a["depreciation_lines"] = fetchall(conn,
            "SELECT * FROM asset_depreciation_lines WHERE asset_id=%s ORDER BY date", (aid,))
        return a

@app.put("/api/assets/{aid}")
def update_asset(aid: int, data: AssetIn, ctx=Depends(get_user)):
    with get_db() as conn:
        asset = fetchone(conn, "SELECT state FROM assets WHERE id=%s AND company_id=%s", (aid, ctx["company_id"]))
        if not asset or asset["state"] == "disposed":
            raise HTTPException(400, "Cannot update disposed asset")
        purchase_date = date.fromisoformat(data.purchase_date) if data.purchase_date else None
        in_service_date = date.fromisoformat(data.in_service_date) if data.in_service_date else None
        return execute(conn,
            "UPDATE assets SET name=%s,asset_number=%s,category_id=%s,purchase_date=%s,in_service_date=%s,"
            "purchase_value=%s,salvage_value=%s,useful_life=%s,depreciation_method=%s,"
            "asset_account_id=%s,depreciation_account_id=%s,expense_account_id=%s,"
            "partner_id=%s,location=%s,serial_number=%s,notes=%s WHERE id=%s AND company_id=%s RETURNING *",
            (data.name, data.asset_number, data.category_id, purchase_date, in_service_date,
             data.purchase_value, data.salvage_value, data.useful_life, data.depreciation_method,
             data.asset_account_id, data.depreciation_account_id, data.expense_account_id,
             data.partner_id, data.location, data.serial_number, data.notes, aid, ctx["company_id"]))

@app.post("/api/assets/{aid}/confirm")
def confirm_asset(aid: int, ctx=Depends(get_user)):
    """Set asset to 'active' and compute depreciation schedule."""
    with get_db() as conn:
        asset = fetchone(conn, "SELECT * FROM assets WHERE id=%s AND company_id=%s", (aid, ctx["company_id"]))
        if not asset or asset["state"] != "draft":
            raise HTTPException(400, "Asset must be in draft state")
        execute(conn, "UPDATE assets SET state='active',book_value=%s WHERE id=%s",
                (asset["purchase_value"], aid))
        # Compute straight-line depreciation schedule
        purchase_val = float(asset["purchase_value"])
        salvage_val  = float(asset["salvage_value"])
        useful_life  = int(asset["useful_life"])
        depreciable  = purchase_val - salvage_val
        if depreciable > 0 and useful_life > 0:
            annual_dep = round(depreciable / useful_life, 2)
            start_date = (asset["in_service_date"] or asset["purchase_date"] or date.today())
            if not isinstance(start_date, date):
                start_date = date.fromisoformat(str(start_date))
            c = dictcur(conn)
            for year in range(useful_life):
                dep_date = start_date.replace(year=start_date.year + year + 1)
                c.execute(
                    "INSERT INTO asset_depreciation_lines (asset_id,company_id,date,amount,book_value_after) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (aid, ctx["company_id"], dep_date, annual_dep,
                     round(purchase_val - annual_dep * (year + 1), 2)))
        return fetchone(conn, "SELECT * FROM assets WHERE id=%s", (aid,))

@app.post("/api/assets/{aid}/depreciate/{line_id}")
def post_depreciation_line(aid: int, line_id: int, ctx=Depends(get_user)):
    """Post a single depreciation line (creates journal entry)."""
    with get_db() as conn:
        asset = fetchone(conn, "SELECT * FROM assets WHERE id=%s AND company_id=%s", (aid, ctx["company_id"]))
        if not asset or asset["state"] != "active":
            raise HTTPException(400, "Asset must be active")
        line = fetchone(conn, "SELECT * FROM asset_depreciation_lines WHERE id=%s AND asset_id=%s AND state='draft'",
                        (line_id, aid))
        if not line:
            raise HTTPException(404, "Depreciation line not found or already posted")

        dep_amount = float(line["amount"])
        dep_acct = asset.get("depreciation_account_id")
        exp_acct = asset.get("expense_account_id")
        if not dep_acct or not exp_acct:
            raise HTTPException(400, "Asset is missing depreciation or expense accounts")

        dep_date = line["date"] if isinstance(line["date"], date) else date.fromisoformat(str(line["date"]))
        gen_journal = fetchone(conn,
            "SELECT id FROM journals WHERE company_id=%s AND type='general' LIMIT 1", (ctx["company_id"],))
        if not gen_journal:
            raise HTTPException(400, "No general journal found")

        name = next_sequence(conn, gen_journal["id"], dep_date)
        c = dictcur(conn)
        c.execute(
            "INSERT INTO moves (company_id,name,move_type,state,date,journal_id,amount_total,narration,created_by) "
            "VALUES (%s,%s,'entry','posted',%s,%s,%s,%s,%s) RETURNING id",
            (ctx["company_id"], name, dep_date, gen_journal["id"], dep_amount,
             f"Depreciation: {asset['name']}", ctx["user_id"]))
        move_id = c.fetchone()["id"]

        for acct_id, debit, credit in [(exp_acct, dep_amount, 0), (dep_acct, 0, dep_amount)]:
            c.execute("INSERT INTO move_lines (move_id,company_id,account_id,name,debit,credit) VALUES (%s,%s,%s,%s,%s,%s)",
                      (move_id, ctx["company_id"], acct_id, f"Depreciation: {asset['name']}", debit, credit))

        new_accum = float(asset["accumulated_depreciation"]) + dep_amount
        new_book  = float(asset["purchase_value"]) - new_accum
        c.execute("UPDATE assets SET accumulated_depreciation=%s,book_value=%s WHERE id=%s",
                  (new_accum, new_book, aid))
        c.execute("UPDATE asset_depreciation_lines SET state='posted',move_id=%s WHERE id=%s", (move_id, line_id))
        return fetchone(conn, "SELECT * FROM assets WHERE id=%s", (aid,))

@app.post("/api/assets/{aid}/dispose")
def dispose_asset(aid: int, body: dict, ctx=Depends(get_user)):
    """Dispose (retire) an asset."""
    with get_db() as conn:
        asset = fetchone(conn, "SELECT * FROM assets WHERE id=%s AND company_id=%s", (aid, ctx["company_id"]))
        if not asset or asset["state"] != "active":
            raise HTTPException(400, "Only active assets can be disposed")
        execute(conn, "UPDATE assets SET state='disposed',active=FALSE WHERE id=%s", (aid,))
        execute(conn, "UPDATE asset_depreciation_lines SET state='cancelled' WHERE asset_id=%s AND state='draft'", (aid,))
        return {"ok": True, "message": f"Asset '{asset['name']}' disposed"}


# ── CRM ───────────────────────────────────────────────────────
CRM_STAGES = ["new", "qualified", "proposition", "won", "lost"]

@app.get("/api/crm/leads")
def list_leads(stage: Optional[str] = None, search: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = ("SELECT l.*, p.name AS partner_name, u.name AS assigned_to "
               "FROM crm_leads l "
               "LEFT JOIN partners p ON p.id=l.partner_id "
               "LEFT JOIN users u ON u.id=l.assigned_user_id "
               "WHERE l.company_id=%s AND l.active=TRUE")
        params: list = [ctx["company_id"]]
        if stage:
            sql += " AND l.stage=%s"; params.append(stage)
        if search:
            sql += " AND (l.name ILIKE %s OR l.contact_name ILIKE %s OR l.email ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        sql += " ORDER BY l.created_at DESC"
        return fetchall(conn, sql, params)

@app.post("/api/crm/leads")
def create_lead(data: LeadIn, ctx=Depends(get_user)):
    with get_db() as conn:
        closing = date.fromisoformat(data.closing_date) if data.closing_date else None
        return execute(conn,
            "INSERT INTO crm_leads (company_id,name,partner_id,contact_name,email,phone,stage,priority,"
            "expected_revenue,probability,assigned_user_id,description,closing_date) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.name, data.partner_id, data.contact_name, data.email, data.phone,
             data.stage, data.priority, data.expected_revenue, data.probability,
             data.assigned_user_id, data.description, closing))

@app.get("/api/crm/leads/{lid}")
def get_lead(lid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        l = fetchone(conn, "SELECT * FROM crm_leads WHERE id=%s AND company_id=%s", (lid, ctx["company_id"]))
        if not l: raise HTTPException(404)
        return l

@app.put("/api/crm/leads/{lid}")
def update_lead(lid: int, data: LeadIn, ctx=Depends(get_user)):
    with get_db() as conn:
        closing = date.fromisoformat(data.closing_date) if data.closing_date else None
        return execute(conn,
            "UPDATE crm_leads SET name=%s,partner_id=%s,contact_name=%s,email=%s,phone=%s,stage=%s,priority=%s,"
            "expected_revenue=%s,probability=%s,assigned_user_id=%s,description=%s,closing_date=%s,updated_at=NOW() "
            "WHERE id=%s AND company_id=%s RETURNING *",
            (data.name, data.partner_id, data.contact_name, data.email, data.phone, data.stage, data.priority,
             data.expected_revenue, data.probability, data.assigned_user_id, data.description, closing,
             lid, ctx["company_id"]))

@app.delete("/api/crm/leads/{lid}")
def delete_lead(lid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE crm_leads SET active=FALSE WHERE id=%s AND company_id=%s", (lid, ctx["company_id"]))
        return {"ok": True}


# ── HR ────────────────────────────────────────────────────────
@app.get("/api/hr/employees")
def list_employees(search: Optional[str] = None, department: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = "SELECT * FROM hr_employees WHERE company_id=%s AND active=TRUE"
        params: list = [ctx["company_id"]]
        if search:
            sql += " AND (name ILIKE %s OR employee_number ILIKE %s OR job_title ILIKE %s)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        if department:
            sql += " AND department=%s"; params.append(department)
        sql += " ORDER BY name"
        return fetchall(conn, sql, params)

@app.post("/api/hr/employees")
def create_employee(data: EmployeeIn, ctx=Depends(get_user)):
    with get_db() as conn:
        hire_date = date.fromisoformat(data.hire_date) if data.hire_date else None
        return execute(conn,
            "INSERT INTO hr_employees (company_id,name,employee_number,job_title,department,email,phone,"
            "nationality,id_number,passport_number,hire_date,contract_type,basic_salary,housing_allowance,transport_allowance) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.name, data.employee_number, data.job_title, data.department,
             data.email, data.phone, data.nationality, data.id_number, data.passport_number,
             hire_date, data.contract_type, data.basic_salary, data.housing_allowance, data.transport_allowance))

@app.get("/api/hr/employees/{eid}")
def get_employee(eid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        e = fetchone(conn, "SELECT * FROM hr_employees WHERE id=%s AND company_id=%s", (eid, ctx["company_id"]))
        if not e: raise HTTPException(404)
        return e

@app.put("/api/hr/employees/{eid}")
def update_employee(eid: int, data: EmployeeIn, ctx=Depends(get_user)):
    with get_db() as conn:
        hire_date = date.fromisoformat(data.hire_date) if data.hire_date else None
        return execute(conn,
            "UPDATE hr_employees SET name=%s,employee_number=%s,job_title=%s,department=%s,email=%s,phone=%s,"
            "nationality=%s,id_number=%s,passport_number=%s,hire_date=%s,contract_type=%s,"
            "basic_salary=%s,housing_allowance=%s,transport_allowance=%s WHERE id=%s AND company_id=%s RETURNING *",
            (data.name, data.employee_number, data.job_title, data.department, data.email, data.phone,
             data.nationality, data.id_number, data.passport_number, hire_date, data.contract_type,
             data.basic_salary, data.housing_allowance, data.transport_allowance, eid, ctx["company_id"]))

@app.delete("/api/hr/employees/{eid}")
def delete_employee(eid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE hr_employees SET active=FALSE WHERE id=%s AND company_id=%s", (eid, ctx["company_id"]))
        return {"ok": True}

@app.get("/api/hr/leaves")
def list_leaves(employee_id: Optional[int] = None, state: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = ("SELECT l.*, e.name AS employee_name FROM hr_leaves l "
               "JOIN hr_employees e ON e.id=l.employee_id WHERE l.company_id=%s")
        params: list = [ctx["company_id"]]
        if employee_id:
            sql += " AND l.employee_id=%s"; params.append(employee_id)
        if state:
            sql += " AND l.state=%s"; params.append(state)
        sql += " ORDER BY l.date_from DESC"
        return fetchall(conn, sql, params)

@app.post("/api/hr/leaves")
def create_leave(data: LeaveIn, ctx=Depends(get_user)):
    with get_db() as conn:
        df = date.fromisoformat(data.date_from)
        dt = date.fromisoformat(data.date_to)
        days = data.days or float((dt - df).days + 1)
        return execute(conn,
            "INSERT INTO hr_leaves (company_id,employee_id,leave_type,date_from,date_to,days,notes) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.employee_id, data.leave_type, df, dt, days, data.notes))

@app.put("/api/hr/leaves/{lid}/approve")
def approve_leave(lid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE hr_leaves SET state='approved' WHERE id=%s AND company_id=%s", (lid, ctx["company_id"]))
        return {"ok": True}

@app.put("/api/hr/leaves/{lid}/refuse")
def refuse_leave(lid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE hr_leaves SET state='refused' WHERE id=%s AND company_id=%s", (lid, ctx["company_id"]))
        return {"ok": True}


# ── Projects ──────────────────────────────────────────────────
@app.get("/api/projects")
def list_projects(state: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = ("SELECT p.*, c.name AS client_name, u.name AS manager_name, "
               "COUNT(t.id) AS task_count "
               "FROM projects p "
               "LEFT JOIN partners c ON c.id=p.partner_id "
               "LEFT JOIN users u ON u.id=p.manager_user_id "
               "LEFT JOIN project_tasks t ON t.project_id=p.id AND t.active=TRUE "
               "WHERE p.company_id=%s AND p.active=TRUE")
        params: list = [ctx["company_id"]]
        if state:
            sql += " AND p.state=%s"; params.append(state)
        sql += " GROUP BY p.id, c.name, u.name ORDER BY p.name"
        return fetchall(conn, sql, params)

@app.post("/api/projects")
def create_project(data: ProjectIn, ctx=Depends(get_user)):
    with get_db() as conn:
        ds = date.fromisoformat(data.date_start) if data.date_start else None
        de = date.fromisoformat(data.date_end)   if data.date_end   else None
        return execute(conn,
            "INSERT INTO projects (company_id,name,partner_id,manager_user_id,state,date_start,date_end,description) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.name, data.partner_id, data.manager_user_id,
             data.state, ds, de, data.description))

@app.get("/api/projects/{pid}")
def get_project(pid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        p = fetchone(conn, "SELECT * FROM projects WHERE id=%s AND company_id=%s", (pid, ctx["company_id"]))
        if not p: raise HTTPException(404)
        p["tasks"] = fetchall(conn,
            "SELECT t.*, u.name AS assigned_to FROM project_tasks t "
            "LEFT JOIN users u ON u.id=t.assigned_user_id "
            "WHERE t.project_id=%s AND t.active=TRUE ORDER BY t.stage,t.name", (pid,))
        return p

@app.put("/api/projects/{pid}")
def update_project(pid: int, data: ProjectIn, ctx=Depends(get_user)):
    with get_db() as conn:
        ds = date.fromisoformat(data.date_start) if data.date_start else None
        de = date.fromisoformat(data.date_end)   if data.date_end   else None
        return execute(conn,
            "UPDATE projects SET name=%s,partner_id=%s,manager_user_id=%s,state=%s,date_start=%s,date_end=%s,description=%s "
            "WHERE id=%s AND company_id=%s RETURNING *",
            (data.name, data.partner_id, data.manager_user_id, data.state, ds, de, data.description, pid, ctx["company_id"]))

@app.delete("/api/projects/{pid}")
def delete_project(pid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE projects SET active=FALSE WHERE id=%s AND company_id=%s", (pid, ctx["company_id"]))
        return {"ok": True}

@app.get("/api/tasks")
def list_tasks(project_id: Optional[int] = None, stage: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = ("SELECT t.*, p.name AS project_name, u.name AS assigned_to "
               "FROM project_tasks t "
               "LEFT JOIN projects p ON p.id=t.project_id "
               "LEFT JOIN users u ON u.id=t.assigned_user_id "
               "WHERE t.company_id=%s AND t.active=TRUE")
        params: list = [ctx["company_id"]]
        if project_id:
            sql += " AND t.project_id=%s"; params.append(project_id)
        if stage:
            sql += " AND t.stage=%s"; params.append(stage)
        sql += " ORDER BY t.stage, t.name"
        return fetchall(conn, sql, params)

@app.post("/api/tasks")
def create_task(data: TaskIn, ctx=Depends(get_user)):
    with get_db() as conn:
        deadline = date.fromisoformat(data.deadline) if data.deadline else None
        return execute(conn,
            "INSERT INTO project_tasks (company_id,project_id,name,assigned_user_id,stage,priority,deadline,description,planned_hours) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.project_id, data.name, data.assigned_user_id,
             data.stage, data.priority, deadline, data.description, data.planned_hours))

@app.put("/api/tasks/{tid}")
def update_task(tid: int, data: TaskIn, ctx=Depends(get_user)):
    with get_db() as conn:
        deadline = date.fromisoformat(data.deadline) if data.deadline else None
        return execute(conn,
            "UPDATE project_tasks SET project_id=%s,name=%s,assigned_user_id=%s,stage=%s,priority=%s,"
            "deadline=%s,description=%s,planned_hours=%s WHERE id=%s AND company_id=%s RETURNING *",
            (data.project_id, data.name, data.assigned_user_id, data.stage, data.priority,
             deadline, data.description, data.planned_hours, tid, ctx["company_id"]))

@app.delete("/api/tasks/{tid}")
def delete_task(tid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE project_tasks SET active=FALSE WHERE id=%s AND company_id=%s", (tid, ctx["company_id"]))
        return {"ok": True}

@app.get("/api/timesheets")
def list_timesheets(project_id: Optional[int] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = ("SELECT ts.*, p.name AS project_name, t.name AS task_name, e.name AS employee_name "
               "FROM timesheets ts "
               "LEFT JOIN projects p ON p.id=ts.project_id "
               "LEFT JOIN project_tasks t ON t.id=ts.task_id "
               "LEFT JOIN hr_employees e ON e.id=ts.employee_id "
               "WHERE ts.company_id=%s")
        params: list = [ctx["company_id"]]
        if project_id:
            sql += " AND ts.project_id=%s"; params.append(project_id)
        sql += " ORDER BY ts.date DESC"
        return fetchall(conn, sql, params)

@app.post("/api/timesheets")
def create_timesheet(data: TimesheetIn, ctx=Depends(get_user)):
    with get_db() as conn:
        ts_date = date.fromisoformat(data.date)
        row = execute(conn,
            "INSERT INTO timesheets (company_id,project_id,task_id,employee_id,date,description,hours) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.project_id, data.task_id, data.employee_id,
             ts_date, data.description, data.hours))
        if data.task_id:
            execute(conn,
                "UPDATE project_tasks SET effective_hours = effective_hours + %s WHERE id=%s",
                (data.hours, data.task_id))
        return row


# ── Expenses ──────────────────────────────────────────────────
@app.get("/api/expenses")
def list_expenses(state: Optional[str] = None, ctx=Depends(get_user)):
    with get_db() as conn:
        sql = ("SELECT e.*, emp.name AS employee_name, ec.name AS category_name "
               "FROM expenses e "
               "LEFT JOIN hr_employees emp ON emp.id=e.employee_id "
               "LEFT JOIN expense_categories ec ON ec.id=e.category_id "
               "WHERE e.company_id=%s")
        params: list = [ctx["company_id"]]
        if state:
            sql += " AND e.state=%s"; params.append(state)
        sql += " ORDER BY e.date DESC"
        return fetchall(conn, sql, params)

@app.post("/api/expenses")
def create_expense(data: ExpenseIn, ctx=Depends(get_user)):
    with get_db() as conn:
        exp_date = date.fromisoformat(data.date)
        return execute(conn,
            "INSERT INTO expenses (company_id,employee_id,category_id,name,date,amount,tax_id,notes) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (ctx["company_id"], data.employee_id, data.category_id, data.name,
             exp_date, data.amount, data.tax_id, data.notes))

@app.put("/api/expenses/{eid}/approve")
def approve_expense(eid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE expenses SET state='approved' WHERE id=%s AND company_id=%s", (eid, ctx["company_id"]))
        return {"ok": True}

@app.put("/api/expenses/{eid}/refuse")
def refuse_expense(eid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE expenses SET state='refused' WHERE id=%s AND company_id=%s", (eid, ctx["company_id"]))
        return {"ok": True}


# ── Company Users ─────────────────────────────────────────────
@app.get("/api/users")
def list_users(ctx=Depends(get_user)):
    with get_db() as conn:
        return fetchall(conn,
            "SELECT id, name, email, role, active, created_at FROM users WHERE company_id=%s ORDER BY name",
            (ctx["company_id"],))

@app.post("/api/users")
def create_user(data: UserIn, ctx=Depends(get_user)):
    with get_db() as conn:
        existing = fetchone(conn, "SELECT id FROM users WHERE email=%s", (data.email,))
        if existing:
            raise HTTPException(400, "Email already in use")
        phash = pwd_ctx.hash(data.password)
        return execute(conn,
            "INSERT INTO users (name,email,password_hash,role,company_id) VALUES (%s,%s,%s,%s,%s) RETURNING id,name,email,role,active",
            (data.name, data.email, phash, data.role, ctx["company_id"]))

@app.put("/api/users/{uid}")
def update_user(uid: int, data: dict, ctx=Depends(get_user)):
    with get_db() as conn:
        allowed = {k: v for k, v in data.items() if k in ("name", "role", "active")}
        if not allowed:
            raise HTTPException(400, "Nothing to update")
        set_clause = ", ".join(f"{k}=%s" for k in allowed)
        vals = list(allowed.values()) + [uid, ctx["company_id"]]
        return execute(conn, f"UPDATE users SET {set_clause} WHERE id=%s AND company_id=%s RETURNING id,name,email,role,active", vals)

@app.delete("/api/users/{uid}")
def delete_user(uid: int, ctx=Depends(get_user)):
    with get_db() as conn:
        execute(conn, "UPDATE users SET active=FALSE WHERE id=%s AND company_id=%s", (uid, ctx["company_id"]))
        return {"ok": True}


# ── Portal Integration ────────────────────────────────────────
PORTAL_API_KEY = os.getenv("PORTAL_API_KEY", "mumtaz-portal-key-change-me")

@app.post("/api/portal/provision")
def portal_provision(data: PortalProvisionIn):
    """Called by app.mumtaz.digital after onboarding to create a tenant. Idempotent."""
    if data.portal_api_key != PORTAL_API_KEY:
        raise HTTPException(403, "Invalid portal API key")
    enabled = data.modules if data.modules else ALL_MODULES
    with get_db() as conn:
        existing_user = fetchone(conn, "SELECT id, company_id FROM users WHERE email=%s", (data.admin_email,))
        if existing_user:
            # Already provisioned — return existing company info
            company_id = existing_user["company_id"]
            return {
                "company_id": company_id,
                "erp_url": "https://erp.mumtaz.digital",
                "message": f"Tenant already provisioned",
                "already_existed": True,
            }
        c = dictcur(conn)
        c.execute(
            "INSERT INTO companies (name, vat_number) VALUES (%s, NULL) RETURNING id",
            (data.company_name,))
        company_id = c.fetchone()["id"]
        seed_company(conn, company_id, enabled_modules=enabled)
        phash = pwd_ctx.hash(data.admin_password)
        c.execute(
            "INSERT INTO users (name,email,password_hash,role,company_id) VALUES ('Admin',%s,%s,'admin',%s) RETURNING id",
            (data.admin_email, phash, company_id))
        user_id = c.fetchone()["id"]
        token = make_token(user_id, company_id)
        return {
            "company_id": company_id,
            "access_token": token,
            "erp_url": "https://erp.mumtaz.digital",
            "message": f"Tenant '{data.company_name}' provisioned",
            "already_existed": False,
        }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "mumtaz-erp"}


# ── Super Admin Setup ─────────────────────────────────────────
@app.get("/api/setup/super-status")
def super_status():
    with get_db() as conn:
        row = fetchone(conn, "SELECT COUNT(*) AS n FROM users WHERE is_super_admin=TRUE")
        return {"has_super": row is not None and int(row["n"]) > 0}

@app.post("/api/setup/super")
def create_super_admin(data: SuperAdminIn):
    with get_db() as conn:
        existing = fetchone(conn, "SELECT id FROM users WHERE is_super_admin=TRUE LIMIT 1")
        if existing:
            raise HTTPException(400, "Super admin already exists")
        phash = pwd_ctx.hash(data.password)
        c = dictcur(conn)
        c.execute(
            "INSERT INTO users (name, email, password_hash, role, is_super_admin, company_id) "
            "VALUES (%s, %s, %s, 'admin', TRUE, NULL) RETURNING id",
            (data.name, data.email, phash)
        )
        user_id = c.fetchone()["id"]
        token = make_token(user_id, None, is_super=True)
        return {"access_token": token, "user": {"id": user_id, "name": data.name,
                                                  "email": data.email, "is_super": True}}


# ── Tenant Module Access ──────────────────────────────────────
@app.get("/api/me/modules")
def get_my_modules(ctx=Depends(get_user)):
    if ctx.get("is_super"):
        return ALL_MODULES
    with get_db() as conn:
        rows = fetchall(conn,
            "SELECT module FROM tenant_modules WHERE company_id=%s AND enabled=TRUE",
            (ctx["company_id"],))
        return [r["module"] for r in rows]

@app.get("/api/modules")
def get_module_catalog(ctx=Depends(get_user)):
    return MODULES


# ── Super Admin: Tenant Management ───────────────────────────
@app.get("/api/super/tenants")
def list_tenants(ctx=Depends(require_super)):
    with get_db() as conn:
        tenants = fetchall(conn,
            """SELECT c.*,
               (SELECT COUNT(*) FROM users u WHERE u.company_id=c.id AND NOT COALESCE(u.is_super_admin,FALSE)) AS user_count,
               (SELECT COUNT(*) FROM moves m WHERE m.company_id=c.id AND m.state='posted') AS posted_moves,
               (SELECT COALESCE(SUM(amount_total),0) FROM moves m WHERE m.company_id=c.id AND m.move_type='out_invoice' AND m.state='posted') AS total_invoiced
               FROM companies c ORDER BY c.id""")
        # Attach enabled modules per tenant
        for t in tenants:
            rows = fetchall(conn,
                "SELECT module FROM tenant_modules WHERE company_id=%s AND enabled=TRUE", (t["id"],))
            t["enabled_modules"] = [r["module"] for r in rows]
        return tenants

@app.post("/api/super/tenants")
def create_tenant(data: TenantIn, ctx=Depends(require_super)):
    with get_db() as conn:
        # Check email not taken
        existing = fetchone(conn, "SELECT id FROM users WHERE email=%s", (data.admin_email,))
        if existing:
            raise HTTPException(400, f"Email {data.admin_email} already in use")
        c = dictcur(conn)
        c.execute(
            "INSERT INTO companies (name, vat_number, phone) VALUES (%s, %s, %s) RETURNING id",
            (data.company_name, data.vat_number, data.phone)
        )
        company_id = c.fetchone()["id"]
        seed_company(conn, company_id, enabled_modules=data.modules)
        phash = pwd_ctx.hash(data.admin_password)
        c.execute(
            "INSERT INTO users (name, email, password_hash, role, company_id) "
            "VALUES ('Admin', %s, %s, 'admin', %s) RETURNING id",
            (data.admin_email, phash, company_id)
        )
        return {"company_id": company_id, "message": f"Tenant '{data.company_name}' created"}

@app.put("/api/super/tenants/{tid}/status")
def update_tenant_status(tid: int, body: StatusUpdate, ctx=Depends(require_super)):
    with get_db() as conn:
        execute(conn, "UPDATE companies SET status=%s WHERE id=%s", (body.status, tid))
        return {"ok": True, "status": body.status}

@app.get("/api/super/tenants/{tid}/modules")
def get_tenant_modules(tid: int, ctx=Depends(require_super)):
    with get_db() as conn:
        rows = fetchall(conn,
            "SELECT module, enabled FROM tenant_modules WHERE company_id=%s", (tid,))
        result = {m: False for m in ALL_MODULES}
        for r in rows:
            result[r["module"]] = bool(r["enabled"])
        return result

@app.put("/api/super/tenants/{tid}/modules")
def update_tenant_modules(tid: int, data: ModuleToggle, ctx=Depends(require_super)):
    with get_db() as conn:
        c = dictcur(conn)
        for module in ALL_MODULES:
            enabled = module in data.modules
            c.execute(
                "INSERT INTO tenant_modules (company_id, module, enabled) VALUES (%s, %s, %s) "
                "ON CONFLICT (company_id, module) DO UPDATE SET enabled=%s",
                (tid, module, enabled, enabled)
            )
        return {"ok": True, "enabled": data.modules}

@app.get("/api/super/tenants/{tid}")
def get_tenant(tid: int, ctx=Depends(require_super)):
    with get_db() as conn:
        tenant = fetchone(conn, "SELECT * FROM companies WHERE id=%s", (tid,))
        if not tenant: raise HTTPException(404)
        tenant["users"] = fetchall(conn,
            "SELECT id,name,email,role,active FROM users WHERE company_id=%s ORDER BY name", (tid,))
        rows = fetchall(conn, "SELECT module,enabled FROM tenant_modules WHERE company_id=%s", (tid,))
        tenant["modules"] = {r["module"]: bool(r["enabled"]) for r in rows}
        return tenant

@app.put("/api/super/tenants/{tid}")
def update_tenant(tid: int, data: TenantUpdateIn, ctx=Depends(require_super)):
    with get_db() as conn:
        updates = {k: v for k, v in data.dict().items() if v is not None}
        if "company_name" in updates:
            updates["name"] = updates.pop("company_name")
        if not updates: raise HTTPException(400, "Nothing to update")
        set_clause = ", ".join(f"{k}=%s" for k in updates)
        vals = list(updates.values()) + [tid]
        return execute(conn, f"UPDATE companies SET {set_clause} WHERE id=%s RETURNING *", vals)

@app.delete("/api/super/tenants/{tid}")
def delete_tenant(tid: int, ctx=Depends(require_super)):
    with get_db() as conn:
        execute(conn, "UPDATE companies SET status='deleted' WHERE id=%s", (tid,))
        execute(conn, "UPDATE users SET active=FALSE WHERE company_id=%s", (tid,))
        return {"ok": True}

@app.get("/api/super/tenants/{tid}/users")
def list_tenant_users(tid: int, ctx=Depends(require_super)):
    with get_db() as conn:
        return fetchall(conn,
            "SELECT id,name,email,role,active,created_at FROM users WHERE company_id=%s ORDER BY name", (tid,))

@app.post("/api/super/tenants/{tid}/users")
def add_tenant_user(tid: int, data: UserIn, ctx=Depends(require_super)):
    with get_db() as conn:
        existing = fetchone(conn, "SELECT id FROM users WHERE email=%s", (data.email,))
        if existing: raise HTTPException(400, "Email already in use")
        phash = pwd_ctx.hash(data.password)
        return execute(conn,
            "INSERT INTO users (name,email,password_hash,role,company_id) VALUES (%s,%s,%s,%s,%s) RETURNING id,name,email,role",
            (data.name, data.email, phash, data.role, tid))

@app.delete("/api/super/tenants/{tid}/users/{uid}")
def remove_tenant_user(tid: int, uid: int, ctx=Depends(require_super)):
    with get_db() as conn:
        execute(conn, "UPDATE users SET active=FALSE WHERE id=%s AND company_id=%s", (uid, tid))
        return {"ok": True}

@app.get("/api/super/stats")
def super_stats(ctx=Depends(require_super)):
    with get_db() as conn:
        total_tenants = fetchone(conn, "SELECT COUNT(*) AS n FROM companies WHERE status!='deleted'")
        active_tenants = fetchone(conn, "SELECT COUNT(*) AS n FROM companies WHERE status='active'")
        total_users = fetchone(conn, "SELECT COUNT(*) AS n FROM users WHERE active=TRUE AND is_super_admin=FALSE")
        total_invoices = fetchone(conn, "SELECT COUNT(*) AS n FROM moves WHERE move_type='out_invoice' AND state='posted'")
        return {
            "total_tenants": int(total_tenants["n"]) if total_tenants else 0,
            "active_tenants": int(active_tenants["n"]) if active_tenants else 0,
            "total_users": int(total_users["n"]) if total_users else 0,
            "total_invoices": int(total_invoices["n"]) if total_invoices else 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Odoo Integration — white-label API bridge
#
#  Each tenant stores their Odoo DB credentials in the companies table.
#  erp-server authenticates to Odoo with a service account and caches the
#  session. All /api/odoo/* endpoints proxy through to the real Odoo instance
#  at the tenant's odoo_url — users never touch Odoo directly.
# ══════════════════════════════════════════════════════════════════════════════

def _get_odoo_session(company_id: int) -> odoo.OdooSession:
    """Load Odoo credentials for company_id and return an authenticated session."""
    with get_db() as conn:
        row = fetchone(conn,
            "SELECT odoo_url, odoo_db, odoo_user, odoo_pass FROM companies WHERE id=%s",
            (company_id,))
    if not row or not row.get("odoo_db"):
        raise HTTPException(400, "This tenant has no Odoo database configured. "
                                  "A super admin must call POST /api/super/tenants/{id}/odoo-connect first.")
    return odoo.get_session(
        row["odoo_url"] or "http://187.77.128.199:8069",
        row["odoo_db"],
        row["odoo_user"] or "admin",
        row["odoo_pass"],
    )

def _odoo_err(exc: OdooError) -> HTTPException:
    if exc.is_not_found():
        return HTTPException(404, exc.message)
    if exc.is_auth_error():
        return HTTPException(401, "Odoo session error — credentials may be wrong.")
    return HTTPException(502, f"Odoo error: {exc.message}")


# ── Super-admin: connect a tenant to an Odoo database ────────────────────────

@app.post("/api/super/tenants/{tid}/odoo-connect")
def odoo_connect(tid: int, data: OdooConnectIn, ctx=Depends(require_super)):
    """Store Odoo DB credentials for a tenant and verify the connection."""
    try:
        sess = odoo.get_session(data.odoo_url, data.odoo_db, data.odoo_user, data.odoo_pass)
        odoo.invalidate_session(data.odoo_url, data.odoo_db, data.odoo_user)
        sess = odoo.get_session(data.odoo_url, data.odoo_db, data.odoo_user, data.odoo_pass)
        info = sess.test_connection()
    except OdooConnectionError as exc:
        raise HTTPException(502, str(exc))
    except OdooError as exc:
        raise _odoo_err(exc)

    with get_db() as conn:
        execute(conn,
            "UPDATE companies SET odoo_url=%s, odoo_db=%s, odoo_user=%s, odoo_pass=%s WHERE id=%s",
            (data.odoo_url, data.odoo_db, data.odoo_user, data.odoo_pass, tid))
    return {**info, "tenant_id": tid, "message": "Odoo credentials saved and connection verified."}


@app.get("/api/super/tenants/{tid}/odoo-test")
def odoo_test(tid: int, ctx=Depends(require_super)):
    """Test the stored Odoo connection for a tenant."""
    try:
        sess = _get_odoo_session(tid)
        return sess.test_connection()
    except OdooConnectionError as exc:
        raise HTTPException(502, str(exc))
    except OdooError as exc:
        raise _odoo_err(exc)


@app.delete("/api/super/tenants/{tid}/odoo-connect")
def odoo_disconnect(tid: int, ctx=Depends(require_super)):
    """Remove Odoo credentials from a tenant."""
    with get_db() as conn:
        row = fetchone(conn, "SELECT odoo_url, odoo_db, odoo_user FROM companies WHERE id=%s", (tid,))
        if row and row.get("odoo_db"):
            odoo.invalidate_session(row["odoo_url"] or "", row["odoo_db"], row["odoo_user"] or "admin")
        execute(conn,
            "UPDATE companies SET odoo_url=NULL, odoo_db=NULL, odoo_user=NULL, odoo_pass=NULL WHERE id=%s",
            (tid,))
    return {"ok": True}


# ── Helpers ────────────────────────────────────────────────────────────────

PARTNER_FIELDS = ["id", "name", "email", "phone", "mobile", "is_company",
                  "customer_rank", "supplier_rank", "street", "city",
                  "country_id", "vat", "ref", "active", "create_date"]

SALE_FIELDS = ["id", "name", "state", "partner_id", "date_order",
               "validity_date", "amount_untaxed", "amount_tax", "amount_total",
               "invoice_status", "note", "order_line"]

INVOICE_FIELDS = ["id", "name", "move_type", "state", "partner_id",
                  "invoice_date", "invoice_date_due", "ref", "narration",
                  "amount_untaxed", "amount_tax", "amount_total", "payment_state",
                  "invoice_line_ids", "invoice_origin"]

PRODUCT_FIELDS = ["id", "name", "default_code", "type", "list_price",
                  "standard_price", "categ_id", "description", "active",
                  "qty_available", "virtual_available"]

INVENTORY_FIELDS = ["id", "product_id", "location_id", "quantity", "reserved_quantity"]

LEAD_FIELDS = ["id", "name", "type", "stage_id", "partner_name", "contact_name",
               "email_from", "phone", "expected_revenue", "probability",
               "partner_id", "description", "create_date", "date_deadline"]


# ── Partners (res.partner) ────────────────────────────────────────────────────

@app.get("/api/odoo/partners")
def odoo_list_partners(
    search: Optional[str] = None,
    is_customer: Optional[bool] = None,
    is_vendor: Optional[bool] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    ctx=Depends(get_user),
):
    sess = _get_odoo_session(ctx["company_id"])
    domain: list = [["active", "=", True]]
    if search:
        domain.append(["name", "ilike", search])
    if is_customer is True:
        domain.append(["customer_rank", ">", 0])
    if is_vendor is True:
        domain.append(["supplier_rank", ">", 0])
    try:
        return sess.search_read("res.partner", domain, PARTNER_FIELDS, limit=limit, offset=offset, order="name asc")
    except OdooError as exc:
        raise _odoo_err(exc)


@app.get("/api/odoo/partners/{pid}")
def odoo_get_partner(pid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        rows = sess.read("res.partner", [pid], PARTNER_FIELDS)
        if not rows:
            raise HTTPException(404, "Partner not found")
        return rows[0]
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/partners", status_code=201)
def odoo_create_partner(data: OdooPartnerIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {
        "name": data.name,
        "is_company": data.is_company,
        "customer_rank": 1 if data.is_customer else 0,
        "supplier_rank": 1 if data.is_vendor else 0,
    }
    for field in ("email", "phone", "mobile", "street", "city", "vat", "ref"):
        v = getattr(data, field)
        if v is not None:
            vals[field] = v
    if data.country_code:
        try:
            countries = sess.search_read("res.country", [["code", "=", data.country_code.upper()]], ["id"], limit=1)
            if countries:
                vals["country_id"] = countries[0]["id"]
        except OdooError:
            pass
    try:
        new_id = sess.create("res.partner", vals)
        rows = sess.read("res.partner", [new_id], PARTNER_FIELDS)
        return rows[0] if rows else {"id": new_id}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.put("/api/odoo/partners/{pid}")
def odoo_update_partner(pid: int, data: OdooPartnerIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {"name": data.name, "is_company": data.is_company,
                  "customer_rank": 1 if data.is_customer else 0,
                  "supplier_rank": 1 if data.is_vendor else 0}
    for field in ("email", "phone", "mobile", "street", "city", "vat", "ref"):
        v = getattr(data, field)
        if v is not None:
            vals[field] = v
    try:
        sess.write("res.partner", [pid], vals)
        rows = sess.read("res.partner", [pid], PARTNER_FIELDS)
        return rows[0] if rows else {"id": pid}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.delete("/api/odoo/partners/{pid}")
def odoo_delete_partner(pid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        sess.write("res.partner", [pid], {"active": False})
        return {"ok": True}
    except OdooError as exc:
        raise _odoo_err(exc)


# ── Sales Orders (sale.order) ─────────────────────────────────────────────────

@app.get("/api/odoo/sales")
def odoo_list_sales(
    state: Optional[str] = None,
    partner_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    ctx=Depends(get_user),
):
    sess = _get_odoo_session(ctx["company_id"])
    domain: list = []
    if state:
        domain.append(["state", "=", state])
    if partner_id:
        domain.append(["partner_id", "=", partner_id])
    if search:
        domain.append(["name", "ilike", search])
    try:
        orders = sess.search_read("sale.order", domain, SALE_FIELDS, limit=limit, offset=offset, order="date_order desc")
        total = sess.search_count("sale.order", domain)
        return {"total": total, "items": orders}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.get("/api/odoo/sales/{sid}")
def odoo_get_sale(sid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        rows = sess.read("sale.order", [sid], SALE_FIELDS)
        if not rows:
            raise HTTPException(404, "Sale order not found")
        order = rows[0]
        if order.get("order_line"):
            order["lines"] = sess.read("sale.order.line", order["order_line"],
                ["id", "product_id", "name", "product_uom_qty", "price_unit", "price_subtotal", "tax_id"])
        return order
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/sales", status_code=201)
def odoo_create_sale(data: OdooSaleIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {"partner_id": data.partner_id}
    if data.date_order:
        vals["date_order"] = data.date_order
    if data.validity_date:
        vals["validity_date"] = data.validity_date
    if data.note:
        vals["note"] = data.note
    if data.order_line:
        vals["order_line"] = [
            (0, 0, {
                "product_id": line.product_id,
                "name": line.name or "",
                "product_uom_qty": line.product_uom_qty,
                "price_unit": line.price_unit,
            })
            for line in data.order_line
        ]
    try:
        new_id = sess.create("sale.order", vals)
        rows = sess.read("sale.order", [new_id], SALE_FIELDS)
        return rows[0] if rows else {"id": new_id}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/sales/{sid}/confirm")
def odoo_confirm_sale(sid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        sess.action_confirm("sale.order", [sid])
        rows = sess.read("sale.order", [sid], ["id", "name", "state"])
        return rows[0] if rows else {"id": sid, "state": "sale"}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/sales/{sid}/cancel")
def odoo_cancel_sale(sid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        sess.call_kw("sale.order", "action_cancel", [[sid]])
        return {"id": sid, "state": "cancel"}
    except OdooError as exc:
        raise _odoo_err(exc)


# ── Invoices (account.move) ───────────────────────────────────────────────────

@app.get("/api/odoo/invoices")
def odoo_list_invoices(
    move_type: str = "out_invoice",
    state: Optional[str] = None,
    partner_id: Optional[int] = None,
    payment_state: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    ctx=Depends(get_user),
):
    sess = _get_odoo_session(ctx["company_id"])
    domain: list = [["move_type", "=", move_type]]
    if state:
        domain.append(["state", "=", state])
    if partner_id:
        domain.append(["partner_id", "=", partner_id])
    if payment_state:
        domain.append(["payment_state", "=", payment_state])
    try:
        invoices = sess.search_read("account.move", domain, INVOICE_FIELDS, limit=limit, offset=offset, order="invoice_date desc")
        total = sess.search_count("account.move", domain)
        return {"total": total, "items": invoices}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.get("/api/odoo/invoices/{iid}")
def odoo_get_invoice(iid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        rows = sess.read("account.move", [iid], INVOICE_FIELDS)
        if not rows:
            raise HTTPException(404, "Invoice not found")
        inv = rows[0]
        if inv.get("invoice_line_ids"):
            inv["lines"] = sess.read("account.move.line", inv["invoice_line_ids"],
                ["id", "product_id", "name", "quantity", "price_unit", "price_subtotal", "tax_ids"])
        return inv
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/invoices", status_code=201)
def odoo_create_invoice(data: OdooInvoiceIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {
        "move_type": data.move_type,
        "partner_id": data.partner_id,
    }
    if data.invoice_date:
        vals["invoice_date"] = data.invoice_date
    if data.invoice_date_due:
        vals["invoice_date_due"] = data.invoice_date_due
    if data.ref:
        vals["ref"] = data.ref
    if data.narration:
        vals["narration"] = data.narration
    if data.invoice_line_ids:
        vals["invoice_line_ids"] = [
            (0, 0, {
                **({"product_id": line.product_id} if line.product_id else {}),
                "name": line.name,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                **({"tax_ids": [(6, 0, line.tax_ids)]} if line.tax_ids else {}),
            })
            for line in data.invoice_line_ids
        ]
    try:
        new_id = sess.create("account.move", vals)
        rows = sess.read("account.move", [new_id], INVOICE_FIELDS)
        return rows[0] if rows else {"id": new_id}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/invoices/{iid}/post")
def odoo_post_invoice(iid: int, ctx=Depends(get_user)):
    """Confirm/post a draft invoice."""
    sess = _get_odoo_session(ctx["company_id"])
    try:
        sess.action_post("account.move", [iid])
        rows = sess.read("account.move", [iid], ["id", "name", "state", "payment_state"])
        return rows[0] if rows else {"id": iid}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/invoices/{iid}/reset")
def odoo_reset_invoice(iid: int, ctx=Depends(get_user)):
    """Reset a posted invoice back to draft."""
    sess = _get_odoo_session(ctx["company_id"])
    try:
        sess.call_kw("account.move", "button_draft", [[iid]])
        return {"id": iid, "state": "draft"}
    except OdooError as exc:
        raise _odoo_err(exc)


# ── Products (product.template / product.product) ─────────────────────────────

@app.get("/api/odoo/products")
def odoo_list_products(
    search: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    ctx=Depends(get_user),
):
    sess = _get_odoo_session(ctx["company_id"])
    domain: list = [["active", "=", True]]
    if search:
        domain.append(["name", "ilike", search])
    if type:
        domain.append(["type", "=", type])
    try:
        products = sess.search_read("product.product", domain, PRODUCT_FIELDS, limit=limit, offset=offset, order="name asc")
        total = sess.search_count("product.product", domain)
        return {"total": total, "items": products}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.get("/api/odoo/products/{pid}")
def odoo_get_product(pid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        rows = sess.read("product.product", [pid], PRODUCT_FIELDS)
        if not rows:
            raise HTTPException(404, "Product not found")
        return rows[0]
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/products", status_code=201)
def odoo_create_product(data: OdooProductIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {
        "name": data.name,
        "type": data.type,
        "list_price": data.list_price,
        "standard_price": data.standard_price,
    }
    for field in ("default_code", "description", "categ_id"):
        v = getattr(data, field)
        if v is not None:
            vals[field] = v
    try:
        new_id = sess.create("product.template", vals)
        rows = sess.search_read("product.product", [["product_tmpl_id", "=", new_id]], PRODUCT_FIELDS, limit=1)
        return rows[0] if rows else {"id": new_id}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.put("/api/odoo/products/{pid}")
def odoo_update_product(pid: int, data: OdooProductIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {
        "name": data.name,
        "type": data.type,
        "list_price": data.list_price,
        "standard_price": data.standard_price,
    }
    for field in ("default_code", "description", "categ_id"):
        v = getattr(data, field)
        if v is not None:
            vals[field] = v
    try:
        sess.write("product.product", [pid], vals)
        rows = sess.read("product.product", [pid], PRODUCT_FIELDS)
        return rows[0] if rows else {"id": pid}
    except OdooError as exc:
        raise _odoo_err(exc)


# ── Inventory (stock.quant) ───────────────────────────────────────────────────

@app.get("/api/odoo/inventory")
def odoo_inventory(
    product_id: Optional[int] = None,
    location: str = "WH/Stock",
    limit: int = Query(200, le=1000),
    ctx=Depends(get_user),
):
    sess = _get_odoo_session(ctx["company_id"])
    domain: list = [["location_id.usage", "=", "internal"]]
    if product_id:
        domain.append(["product_id", "=", product_id])
    if location and location != "all":
        domain.append(["location_id.complete_name", "ilike", location])
    try:
        return sess.search_read("stock.quant", domain, INVENTORY_FIELDS, limit=limit)
    except OdooError as exc:
        raise _odoo_err(exc)


# ── CRM Leads/Opportunities (crm.lead) ────────────────────────────────────────

@app.get("/api/odoo/crm")
def odoo_list_leads(
    type: str = "lead",
    stage_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    ctx=Depends(get_user),
):
    sess = _get_odoo_session(ctx["company_id"])
    domain: list = [["type", "=", type], ["active", "=", True]]
    if stage_id:
        domain.append(["stage_id", "=", stage_id])
    if search:
        domain.append("|", ["name", "ilike", search], ["partner_name", "ilike", search])
    try:
        leads = sess.search_read("crm.lead", domain, LEAD_FIELDS, limit=limit, offset=offset, order="create_date desc")
        total = sess.search_count("crm.lead", domain)
        return {"total": total, "items": leads}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.get("/api/odoo/crm/{lid}")
def odoo_get_lead(lid: int, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    try:
        rows = sess.read("crm.lead", [lid], LEAD_FIELDS)
        if not rows:
            raise HTTPException(404, "Lead not found")
        return rows[0]
    except OdooError as exc:
        raise _odoo_err(exc)


@app.post("/api/odoo/crm", status_code=201)
def odoo_create_lead(data: OdooLeadIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {"name": data.name, "type": data.type}
    for field in ("partner_name", "contact_name", "email_from", "phone", "description", "expected_revenue"):
        v = getattr(data, field)
        if v is not None:
            vals[field] = v
    try:
        new_id = sess.create("crm.lead", vals)
        rows = sess.read("crm.lead", [new_id], LEAD_FIELDS)
        return rows[0] if rows else {"id": new_id}
    except OdooError as exc:
        raise _odoo_err(exc)


@app.put("/api/odoo/crm/{lid}")
def odoo_update_lead(lid: int, data: OdooLeadIn, ctx=Depends(get_user)):
    sess = _get_odoo_session(ctx["company_id"])
    vals: dict = {"name": data.name, "type": data.type}
    for field in ("partner_name", "contact_name", "email_from", "phone", "description", "expected_revenue"):
        v = getattr(data, field)
        if v is not None:
            vals[field] = v
    try:
        sess.write("crm.lead", [lid], vals)
        rows = sess.read("crm.lead", [lid], LEAD_FIELDS)
        return rows[0] if rows else {"id": lid}
    except OdooError as exc:
        raise _odoo_err(exc)


# ── Odoo meta: available databases ───────────────────────────────────────────

@app.get("/api/super/odoo/databases")
def odoo_list_databases(
    url: str = "http://187.77.128.199:8069",
    ctx=Depends(require_super),
):
    """List available Odoo databases on the given server (for the connect wizard)."""
    import json as _json
    import urllib.request as _req
    payload = _json.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": {}}).encode()
    request = _req.Request(url.rstrip("/") + "/web/database/list",
                           data=payload, headers={"Content-Type": "application/json"})
    try:
        with _req.urlopen(request, timeout=10) as resp:
            body = _json.loads(resp.read())
            if "error" in body:
                raise HTTPException(502, body["error"].get("message", "Odoo error"))
            return {"databases": body.get("result", []), "url": url}
    except urllib.error.URLError as exc:
        raise HTTPException(502, f"Cannot reach Odoo at {url}: {exc.reason}")
