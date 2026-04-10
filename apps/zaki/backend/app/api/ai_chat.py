from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from pydantic import BaseModel
from typing import Optional
import anthropic
import json
import uuid
from datetime import datetime, date

from app.db.database import get_db
from app.models.user import User
from app.models.transaction import Transaction, TxType, AISession, AIMessage
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["ai"])

SYSTEM_PROMPT = """You are ZAKI, the AI CFO and trusted financial advisor to the CEO/owner of this business.

Your role: Be a world-class CFO and financial confidant — knowledgeable, decisive, and personal. Think of yourself as the CEO's most trusted financial partner who knows every number in the business and gives straight talk.

## Communication Style
- Lead with the key insight or answer immediately — no fluff preamble
- Be conversational and direct, like a trusted colleague, not a formal report
- Use specific numbers and percentages from the actual data every time
- Be decisive: say "you should..." not "you might consider..."
- For voice/quick questions: keep it concise and punchy
- For analysis requests: use structured markdown with ## headers, tables, and bullets

## Response Format for Analysis
- Start with a 1-2 sentence executive summary (bold the key number)
- Use ## headers to organize sections
- Use markdown tables for comparisons (| Col | Col |)
- Use bullet lists for recommendations
- Flag risks: ⚠️ | Opportunities: ✅ | Critical: 🔴 | Watch: 🟡 | Strong: 🟢
- End with numbered CFO Recommendations

## Your Expertise
P&L analysis, cash flow management, burn rate, runway, expense optimization, revenue analysis, financial ratios, forecasting, budgeting, investment decisions, cost reduction, pricing strategy, financial health scoring.

Always reference the actual financial data provided. Never make up numbers — work with what's there."""


def _get_financial_context(user: User, db: Session) -> str:
    now = datetime.now()
    txs = db.query(Transaction).filter(Transaction.user_id == user.id).order_by(
        Transaction.date.desc()
    ).limit(500).all()

    if not txs:
        return "No financial data available yet. User has not added any transactions."

    # Current month
    curr_month_txs = [t for t in txs if t.date.year == now.year and t.date.month == now.month]
    curr_income  = sum(t.amount for t in curr_month_txs if t.type == TxType.income)
    curr_expense = sum(t.amount for t in curr_month_txs if t.type == TxType.expense)
    curr_net     = curr_income - curr_expense

    # Prior month
    pm = now.month - 1 if now.month > 1 else 12
    py = now.year if now.month > 1 else now.year - 1
    prev_month_txs = [t for t in txs if t.date.year == py and t.date.month == pm]
    prev_income  = sum(t.amount for t in prev_month_txs if t.type == TxType.income)
    prev_expense = sum(t.amount for t in prev_month_txs if t.type == TxType.expense)

    # All-time
    total_income  = sum(t.amount for t in txs if t.type == TxType.income)
    total_expense = sum(t.amount for t in txs if t.type == TxType.expense)

    # Expense categories this month
    cat_map: dict[str, float] = {}
    for t in curr_month_txs:
        if t.type == TxType.expense:
            k = t.category or "Uncategorized"
            cat_map[k] = cat_map.get(k, 0) + t.amount
    top_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)[:6]

    # Recent transactions (last 10)
    recent = txs[:10]
    recent_lines = [
        f"  {t.date} | {t.type.value:8} | ${t.amount:>10,.2f} | {t.category or '—'} | {t.description or '—'}"
        for t in recent
    ]

    # Monthly trend (last 6 months)
    month_data: dict[str, dict] = {}
    for t in txs:
        key = f"{t.date.year}-{t.date.month:02d}"
        if key not in month_data:
            month_data[key] = {"income": 0.0, "expense": 0.0}
        if t.type == TxType.income:
            month_data[key]["income"] += t.amount
        else:
            month_data[key]["expense"] += t.amount
    trend_lines = []
    for k in sorted(month_data.keys())[-6:]:
        d = month_data[k]
        net = d["income"] - d["expense"]
        trend_lines.append(f"  {k}: Income ${d['income']:,.0f} | Expenses ${d['expense']:,.0f} | Net ${net:,.0f}")

    ctx_parts = [
        f"=== FINANCIAL DATA FOR {user.name or user.email} ({user.company or 'Business'}) ===",
        f"",
        f"CURRENT MONTH ({now.strftime('%B %Y')}):",
        f"  Income:   ${curr_income:,.2f}",
        f"  Expenses: ${curr_expense:,.2f}",
        f"  Net:      ${curr_net:,.2f}",
        f"  Expense Ratio: {(curr_expense/curr_income*100):.1f}%" if curr_income > 0 else "  Expense Ratio: N/A",
        f"",
        f"PRIOR MONTH ({now.replace(day=1).strftime('%B') if now.month == 1 else now.replace(month=now.month-1).strftime('%B %Y')}):",
        f"  Income:   ${prev_income:,.2f}",
        f"  Expenses: ${prev_expense:,.2f}",
        f"  Net:      ${prev_income - prev_expense:,.2f}",
        f"",
        f"MONTH-OVER-MONTH CHANGES:",
        f"  Income change:  {((curr_income - prev_income)/prev_income*100):+.1f}%" if prev_income > 0 else "  Income change: N/A",
        f"  Expense change: {((curr_expense - prev_expense)/prev_expense*100):+.1f}%" if prev_expense > 0 else "  Expense change: N/A",
        f"",
        f"ALL-TIME TOTALS ({len(txs)} transactions):",
        f"  Total Income:   ${total_income:,.2f}",
        f"  Total Expenses: ${total_expense:,.2f}",
        f"  Total Net:      ${total_income - total_expense:,.2f}",
        f"",
        f"EXPENSE BREAKDOWN THIS MONTH (top categories):",
    ]
    for cat, amt in top_cats:
        pct = (amt / curr_expense * 100) if curr_expense > 0 else 0
        ctx_parts.append(f"  {cat}: ${amt:,.2f} ({pct:.1f}%)")

    ctx_parts += [
        f"",
        f"6-MONTH TREND:",
        *trend_lines,
        f"",
        f"RECENT TRANSACTIONS (last 10):",
        *recent_lines,
    ]

    return "\n".join(ctx_parts)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(503, "AI service not configured — add ANTHROPIC_API_KEY to .env")

    session = None
    if body.session_id:
        session = db.query(AISession).filter(
            AISession.id == body.session_id, AISession.user_id == user.id
        ).first()
    if not session:
        session = AISession(id=str(uuid.uuid4()), user_id=user.id, title=body.message[:60])
        db.add(session)
        db.commit()

    history = db.query(AIMessage).filter(
        AIMessage.session_id == session.id
    ).order_by(AIMessage.created_at).limit(30).all()

    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": body.message})

    db.add(AIMessage(id=str(uuid.uuid4()), session_id=session.id, role="user", content=body.message))
    db.commit()

    ctx = _get_financial_context(user, db)
    system = f"{SYSTEM_PROMPT}\n\n{ctx}"

    async def generate():
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        full_response = ""
        yield f"data: {json.dumps({'session_id': session.id})}\n\n"
        async with client.messages.stream(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield f"data: {json.dumps({'text': text})}\n\n"

        db.add(AIMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            role="assistant",
            content=full_response,
        ))
        db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sessions = db.query(AISession).filter(
        AISession.user_id == user.id
    ).order_by(AISession.created_at.desc()).limit(20).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions]


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.query(AISession).filter(
        AISession.id == session_id, AISession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")
    messages = db.query(AIMessage).filter(
        AIMessage.session_id == session_id
    ).order_by(AIMessage.created_at).all()
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in messages]
