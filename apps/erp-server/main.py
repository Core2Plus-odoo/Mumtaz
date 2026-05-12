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
def make_token(user_id: int, company_id: int) -> str:
    exp = datetime.utcnow() + timedelta(days=30)
    return jwt.encode({"sub": str(user_id), "cid": company_id, "exp": exp}, SECRET, algorithm=ALGO)

def get_user(authorization: str = Header(...)):
    try:
        scheme, token = authorization.split()
        assert scheme.lower() == "bearer"
        p = jwt.decode(token, SECRET, algorithms=[ALGO])
        return {"user_id": int(p["sub"]), "company_id": p["cid"]}
    except Exception:
        raise HTTPException(401, "Not authenticated")


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


def seed_company(conn, company_id: int):
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


# ── Pydantic models ───────────────────────────────────────────
class LoginIn(BaseModel):
    email: str
    password: str

class SetupIn(BaseModel):
    company_name: str
    admin_email: str
    admin_password: str
    vat_number: Optional[str] = None
    phone: Optional[str] = None

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


# ── Setup ─────────────────────────────────────────────────────
@app.get("/api/setup/status")
def setup_status():
    with get_db() as conn:
        row = fetchone(conn, "SELECT COUNT(*) AS n FROM companies")
        return {"initialized": row and int(row["n"]) > 0}

@app.post("/api/setup/init")
def setup_init(data: SetupIn):
    with get_db() as conn:
        existing = fetchone(conn, "SELECT id FROM companies LIMIT 1")
        if existing:
            raise HTTPException(400, "Already initialized")
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
        token = make_token(user["id"], user["company_id"])
        return {"access_token": token, "user": {"id": user["id"], "name": user["name"],
                                                  "email": user["email"], "role": user["role"]}}

@app.get("/api/auth/me")
def me(ctx=Depends(get_user)):
    with get_db() as conn:
        user = fetchone(conn, "SELECT id,name,email,role,company_id FROM users WHERE id=%s", (ctx["user_id"],))
        if not user:
            raise HTTPException(404, "User not found")
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


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "mumtaz-erp"}
