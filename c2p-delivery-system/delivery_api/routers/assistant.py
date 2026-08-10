"""Assistant router — read-only Q&A over live Odoo and the delivery store.

Endpoints:
  POST /assistant/ask     one question in, an answer plus the rows behind it
  GET  /assistant/tools   what it can look at (the console's empty state)

main.py wires dependencies via init(store); the router never touches main.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import assistant as assistant_mod

router = APIRouter(prefix="/assistant", tags=["assistant"])
_store = None


def init(store) -> None:
    global _store
    _store = store


class AskIn(BaseModel):
    question: str


@router.get("/tools")
def tools():
    return {"tools": assistant_mod.tools_catalog()}


@router.post("/ask")
def ask(body: AskIn):
    try:
        return assistant_mod.ask(_store, body.question)
    except assistant_mod.AssistantError as exc:
        # A configuration or empty-question problem: the caller can fix it, so
        # say what is wrong rather than returning a 500.
        raise HTTPException(status_code=400, detail=str(exc))
