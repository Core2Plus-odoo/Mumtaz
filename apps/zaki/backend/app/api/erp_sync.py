from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
from datetime import date

from app.db.database import get_db
from app.models.user import User
from app.models.transaction import Transaction, TxType, TxSource
from app.core.security import get_current_user
from app.odoo.client import authenticate as odoo_authenticate, search_read

router = APIRouter(prefix="/erp", tags=["erp"])


class ERPConnectRequest(BaseModel):
    odoo_url: str
    db: str
    email: str
    password: str


@router.post("/connect")
async def connect_erp(
    body: ERPConnectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Authenticate against Odoo and save the connection to this user."""
    base_url = body.odoo_url.rstrip("/")
    try:
        odoo = await odoo_authenticate(base_url, body.db, body.email, body.password)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    user.odoo_instance_url = base_url
    user.odoo_db = body.db
    user.odoo_session_id = odoo["session_id"]
    user.odoo_user_id = str(odoo["uid"])
    db.commit()
    return {"status": "connected", "erp_url": base_url, "erp_db": body.db, "name": odoo["name"]}


@router.delete("/disconnect")
def disconnect_erp(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.odoo_session_id = None
    user.odoo_instance_url = None
    user.odoo_db = None
    db.commit()
    return {"status": "disconnected"}


@router.post("/sync")
async def sync_from_erp(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pull invoices and bills from Odoo into ZAKI via standard JSON-RPC."""
    if not user.odoo_session_id or not user.odoo_instance_url:
        raise HTTPException(400, "Odoo not connected. Use /erp/connect first.")

    conn = {
        "base_url":   user.odoo_instance_url,
        "db":         user.odoo_db,
        "session_id": user.odoo_session_id,
    }

    imported = 0

    # ── Invoices (income) ──────────────────────────────────────────
    try:
        invoices = await search_read(
            conn, "account.move",
            [["move_type", "=", "out_invoice"], ["state", "=", "posted"]],
            ["name", "invoice_date", "amount_total", "currency_id", "partner_id", "ref"],
            limit=500, order="invoice_date desc",
        )
        for inv in invoices:
            erp_id = f"inv_{inv['id']}"
            if db.query(Transaction).filter(
                Transaction.erp_id == erp_id,
                Transaction.user_id == user.id,
            ).first():
                continue
            tx = Transaction(
                id=str(uuid.uuid4()),
                user_id=user.id,
                date=_parse_date(inv.get("invoice_date")),
                amount=float(inv.get("amount_total", 0)),
                type=TxType.income,
                category="Invoice",
                description=inv.get("name"),
                reference=inv.get("ref") or (inv["partner_id"][1] if inv.get("partner_id") else None),
                currency=inv["currency_id"][1] if inv.get("currency_id") else "AED",
                source=TxSource.erp_sync,
                erp_id=erp_id,
            )
            db.add(tx)
            imported += 1
    except Exception as exc:
        raise HTTPException(502, f"Odoo invoice fetch failed: {exc}")

    # ── Bills (expenses) ───────────────────────────────────────────
    try:
        bills = await search_read(
            conn, "account.move",
            [["move_type", "=", "in_invoice"], ["state", "=", "posted"]],
            ["name", "invoice_date", "amount_total", "currency_id", "partner_id"],
            limit=500, order="invoice_date desc",
        )
        for bill in bills:
            erp_id = f"bill_{bill['id']}"
            if db.query(Transaction).filter(
                Transaction.erp_id == erp_id,
                Transaction.user_id == user.id,
            ).first():
                continue
            tx = Transaction(
                id=str(uuid.uuid4()),
                user_id=user.id,
                date=_parse_date(bill.get("invoice_date")),
                amount=float(bill.get("amount_total", 0)),
                type=TxType.expense,
                category="Bill",
                description=bill.get("name"),
                reference=bill["partner_id"][1] if bill.get("partner_id") else None,
                currency=bill["currency_id"][1] if bill.get("currency_id") else "AED",
                source=TxSource.erp_sync,
                erp_id=erp_id,
            )
            db.add(tx)
            imported += 1
    except Exception as exc:
        raise HTTPException(502, f"Odoo bill fetch failed: {exc}")

    db.commit()
    return {"synced": imported, "status": "ok"}


def _parse_date(val) -> date:
    from datetime import datetime
    if not val:
        return date.today()
    if isinstance(val, date):
        return val
    return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
