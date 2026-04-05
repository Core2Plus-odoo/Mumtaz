from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx
import uuid
from datetime import date

from app.db.database import get_db
from app.models.user import User
from app.models.transaction import Transaction, TxType, TxSource
from app.core.security import get_current_user

router = APIRouter(prefix="/erp", tags=["erp"])


class ERPConnectRequest(BaseModel):
    odoo_url: str
    api_key: str


@router.post("/connect")
async def connect_erp(
    body: ERPConnectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Validate and save Mumtaz ERP connection."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{body.odoo_url.rstrip('/')}/api/mumtaz/v1/health",
                headers={"X-API-Key": body.api_key},
                timeout=10,
            )
            if resp.status_code != 200:
                raise HTTPException(400, "Invalid API key or ERP URL")
        except httpx.RequestError:
            raise HTTPException(503, "Cannot reach Mumtaz ERP")

    user.erp_api_key = body.api_key
    user.odoo_instance_url = body.odoo_url.rstrip("/")
    db.commit()
    return {"status": "connected", "erp_url": user.odoo_instance_url}


@router.delete("/disconnect")
def disconnect_erp(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.erp_api_key = None
    user.odoo_instance_url = None
    db.commit()
    return {"status": "disconnected"}


@router.post("/sync")
async def sync_from_erp(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pull financial data from Mumtaz ERP into ZAKI."""
    if not user.erp_api_key or not user.odoo_instance_url:
        raise HTTPException(400, "ERP not connected. Connect first via /erp/connect")

    headers = {"X-API-Key": user.erp_api_key}
    base = user.odoo_instance_url

    imported = 0
    async with httpx.AsyncClient() as client:
        # Pull invoices (income)
        try:
            resp = await client.get(f"{base}/api/mumtaz/v1/invoices", headers=headers, timeout=30)
            if resp.status_code == 200:
                for inv in resp.json().get("data", []):
                    erp_id = f"inv_{inv.get('id')}"
                    if db.query(Transaction).filter(Transaction.erp_id == erp_id).first():
                        continue
                    tx = Transaction(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        date=_parse_date(inv.get("invoice_date") or inv.get("date")),
                        amount=float(inv.get("amount_total", 0)),
                        type=TxType.income,
                        category="Invoice",
                        description=inv.get("name"),
                        reference=inv.get("ref"),
                        source=TxSource.erp_sync,
                        erp_id=erp_id,
                    )
                    db.add(tx)
                    imported += 1
        except Exception:
            pass

        # Pull bills (expenses)
        try:
            resp = await client.get(f"{base}/api/mumtaz/v1/bills", headers=headers, timeout=30)
            if resp.status_code == 200:
                for bill in resp.json().get("data", []):
                    erp_id = f"bill_{bill.get('id')}"
                    if db.query(Transaction).filter(Transaction.erp_id == erp_id).first():
                        continue
                    tx = Transaction(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        date=_parse_date(bill.get("invoice_date") or bill.get("date")),
                        amount=float(bill.get("amount_total", 0)),
                        type=TxType.expense,
                        category="Bill",
                        description=bill.get("name"),
                        source=TxSource.erp_sync,
                        erp_id=erp_id,
                    )
                    db.add(tx)
                    imported += 1
        except Exception:
            pass

    db.commit()
    return {"synced": imported, "status": "ok"}


def _parse_date(val) -> date:
    from datetime import datetime
    if not val:
        return date.today()
    if isinstance(val, date):
        return val
    return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
