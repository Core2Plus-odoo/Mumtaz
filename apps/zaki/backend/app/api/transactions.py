from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from pydantic import BaseModel
from datetime import date
from typing import Optional
import uuid

from app.db.database import get_db
from app.models.user import User
from app.models.transaction import Transaction, TxType, TxSource
from app.core.security import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TxCreate(BaseModel):
    date: date
    amount: float
    type: TxType
    category: Optional[str] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    currency: str = "USD"


class TxOut(BaseModel):
    id: str
    date: date
    amount: float
    type: str
    category: Optional[str]
    description: Optional[str]
    reference: Optional[str]
    currency: str
    source: str

    class Config:
        from_attributes = True


@router.get("/", response_model=list[TxOut])
def list_transactions(
    type: Optional[TxType] = None,
    category: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Transaction).filter(Transaction.user_id == user.id)
    if type:
        q = q.filter(Transaction.type == type)
    if category:
        q = q.filter(Transaction.category == category)
    if from_date:
        q = q.filter(Transaction.date >= from_date)
    if to_date:
        q = q.filter(Transaction.date <= to_date)
    return q.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()


@router.post("/", response_model=TxOut, status_code=201)
def create_transaction(
    body: TxCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tx = Transaction(id=str(uuid.uuid4()), user_id=user.id, **body.model_dump())
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(
    tx_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == user.id).first()
    if tx:
        db.delete(tx)
        db.commit()


@router.get("/summary")
def get_summary(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import datetime
    year = year or datetime.now().year
    month = month or datetime.now().month

    q = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month,
    )
    txs = q.all()

    income = sum(t.amount for t in txs if t.type == TxType.income)
    expense = sum(t.amount for t in txs if t.type == TxType.expense)

    # Monthly trend (last 6 months)
    trend = db.query(
        extract('year', Transaction.date).label('year'),
        extract('month', Transaction.date).label('month'),
        Transaction.type,
        func.sum(Transaction.amount).label('total'),
    ).filter(Transaction.user_id == user.id).group_by('year', 'month', Transaction.type).all()

    # Categories breakdown
    cats = db.query(
        Transaction.category,
        func.sum(Transaction.amount).label('total'),
    ).filter(
        Transaction.user_id == user.id,
        Transaction.type == TxType.expense,
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month,
    ).group_by(Transaction.category).all()

    return {
        "income": income,
        "expense": expense,
        "net": income - expense,
        "transaction_count": len(txs),
        "trend": [{"year": int(r.year), "month": int(r.month), "type": r.type, "total": float(r.total)} for r in trend],
        "categories": [{"category": r.category or "Uncategorized", "total": float(r.total)} for r in cats],
    }
