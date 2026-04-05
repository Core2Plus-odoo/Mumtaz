from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import anthropic
import json
import uuid

from app.db.database import get_db
from app.models.user import User
from app.models.transaction import Transaction, TxType, AISession, AIMessage
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["ai"])

SYSTEM_PROMPT = """You are ZAKI, an expert CFO AI assistant for SME businesses.
You help business owners understand their financial data, spot trends, forecast cash flow,
and make smart financial decisions.

Be concise, direct, and use clear financial language. When asked about data,
analyze it and provide actionable insights. Format numbers clearly.
If asked for advice, give specific, practical recommendations.
You can handle voice input — keep responses conversational and scannable."""


def _get_financial_context(user: User, db: Session) -> str:
    txs = db.query(Transaction).filter(Transaction.user_id == user.id).order_by(
        Transaction.date.desc()
    ).limit(200).all()
    if not txs:
        return "No financial data available yet."

    income = sum(t.amount for t in txs if t.type == TxType.income)
    expense = sum(t.amount for t in txs if t.type == TxType.expense)
    return (
        f"Financial summary ({len(txs)} transactions): "
        f"Total Income: ${income:,.2f} | Total Expenses: ${expense:,.2f} | "
        f"Net: ${income - expense:,.2f}"
    )


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
        raise HTTPException(503, "AI service not configured")

    # Get or create session
    session = None
    if body.session_id:
        session = db.query(AISession).filter(
            AISession.id == body.session_id, AISession.user_id == user.id
        ).first()
    if not session:
        session = AISession(id=str(uuid.uuid4()), user_id=user.id, title=body.message[:60])
        db.add(session)
        db.commit()

    # Load history
    history = db.query(AIMessage).filter(
        AIMessage.session_id == session.id
    ).order_by(AIMessage.created_at).limit(20).all()

    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": body.message})

    # Save user message
    db.add(AIMessage(id=str(uuid.uuid4()), session_id=session.id, role="user", content=body.message))
    db.commit()

    ctx = _get_financial_context(user, db)
    system = f"{SYSTEM_PROMPT}\n\nUser financial context: {ctx}"

    async def generate():
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        full_response = ""
        # Stream session_id first
        yield f"data: {json.dumps({'session_id': session.id})}\n\n"
        async with client.messages.stream(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield f"data: {json.dumps({'text': text})}\n\n"

        # Save assistant message
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
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sessions = db.query(AISession).filter(
        AISession.user_id == user.id
    ).order_by(AISession.created_at.desc()).limit(20).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions]


@router.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = db.query(AISession).filter(
        AISession.id == session_id, AISession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")
    messages = db.query(AIMessage).filter(
        AIMessage.session_id == session_id
    ).order_by(AIMessage.created_at).all()
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in messages]
