from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import pandas as pd
import io
import uuid
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.transaction import Transaction, TxType, TxSource
from app.models.upload import Upload
from app.core.security import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])

EXPECTED_COLUMNS = {"date", "amount", "type"}
CATEGORY_MAP = {
    "in": TxType.income, "income": TxType.income, "credit": TxType.income,
    "out": TxType.expense, "expense": TxType.expense, "debit": TxType.expense,
    "transfer": TxType.transfer,
}


@router.post("/csv")
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "Only CSV and Excel files supported")

    content = await file.read()
    upload_record = Upload(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename=file.filename,
        status="processing",
    )
    db.add(upload_record)
    db.commit()

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        df.columns = [c.lower().strip() for c in df.columns]

        missing = EXPECTED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}. Required: date, amount, type")

        rows_ok = 0
        rows_fail = 0
        txs = []

        for _, row in df.iterrows():
            try:
                tx_type_raw = str(row.get("type", "")).lower().strip()
                tx_type = CATEGORY_MAP.get(tx_type_raw)
                if not tx_type:
                    rows_fail += 1
                    continue

                tx_date = pd.to_datetime(row["date"]).date()
                amount = float(row["amount"])
                if amount < 0:
                    amount = abs(amount)

                txs.append(Transaction(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    date=tx_date,
                    amount=amount,
                    type=tx_type,
                    category=str(row.get("category", "")).strip() or None,
                    description=str(row.get("description", row.get("memo", ""))).strip() or None,
                    reference=str(row.get("reference", row.get("ref", ""))).strip() or None,
                    currency=str(row.get("currency", "USD")).strip().upper(),
                    source=TxSource.upload,
                ))
                rows_ok += 1
            except Exception:
                rows_fail += 1

        db.bulk_save_objects(txs)
        upload_record.rows_imported = rows_ok
        upload_record.rows_failed = rows_fail
        upload_record.status = "done"
        db.commit()

        return {
            "upload_id": upload_record.id,
            "filename": file.filename,
            "rows_imported": rows_ok,
            "rows_failed": rows_fail,
            "status": "done",
        }

    except Exception as e:
        upload_record.status = "failed"
        upload_record.error = str(e)
        db.commit()
        raise HTTPException(422, str(e))


@router.get("/template")
def download_template():
    """Return CSV column reference."""
    return {
        "columns": ["date", "amount", "type", "category", "description", "reference", "currency"],
        "type_values": ["income", "expense", "transfer"],
        "example_row": {
            "date": "2026-01-15",
            "amount": 5000,
            "type": "income",
            "category": "Sales",
            "description": "Invoice payment",
            "reference": "INV-001",
            "currency": "USD",
        },
    }
