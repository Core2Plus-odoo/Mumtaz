"""Client Knowledge service — read a slice before acting, write learnings after.

This is the compounding memory: every client-touching agent loads the relevant
slice of what C2P already knows about an account, then appends what it learned.
Retrieval is keyword-based today (see store.search_knowledge); the interface is
deliberately small so a vector backend can replace the internals later without
changing callers.
"""
from __future__ import annotations

import json
from typing import Optional

from models import KnowledgeEntry


class KnowledgeService:
    def __init__(self, store):
        self.store = store

    def read_slice(self, account_id: Optional[str], topic: Optional[str] = None,
                   limit: int = 12) -> list[KnowledgeEntry]:
        if not account_id:
            return []
        if topic:
            return self.store.search_knowledge(account_id, topic, limit=limit)
        return self.store.list_knowledge(account_id, limit=limit)

    def write_entry(self, account_id: str, kind: str, content,
                    title: str = "", learned_by: str = "agent",
                    tags: Optional[list] = None) -> KnowledgeEntry:
        entry = KnowledgeEntry(
            account_id=account_id, kind=kind, content=content,
            title=title or kind.replace("_", " ").title(),
            learned_by=learned_by, tags=tags or [],
        )
        return self.store.add_knowledge(entry)

    def context_block(self, account_id: Optional[str], topic: Optional[str] = None) -> str:
        """A prompt-ready block of prior knowledge, or '' if none. Agents append
        this to their user message so they act with institutional memory."""
        entries = self.read_slice(account_id, topic)
        if not entries:
            return ""
        lines = []
        for e in entries:
            c = e.content if isinstance(e.content, str) else json.dumps(e.content)
            line = f"- [{e.kind}] {e.title}: {c}".strip()
            lines.append(line[:600])
        return ("\n\nWHAT C2P ALREADY KNOWS ABOUT THIS CLIENT "
                "(use it; stay consistent; do not re-ask):\n" + "\n".join(lines) + "\n")
