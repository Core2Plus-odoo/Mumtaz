"""Autonomy policy — the enforcement seam for the approval layer.

A config map of action → level (auto | approval). Anything client-facing, that
costs money, or is irreversible is `approval` and routes through a human; the
rest runs `auto`. The per-tenant override lives in app_settings('autonomy'), so
an owner can tighten or loosen policy without a code change. Every gated action
calls `gate()`, which creates a pending Approval and withholds the action until
a human decides.
"""
from __future__ import annotations

from typing import Optional

from models import Approval

# Defaults. Internal/reversible agent reasoning is auto; client-facing, money,
# or production-code actions are gated.
AUTONOMY: dict[str, str] = {
    "prospect": "auto",
    "research": "auto",
    "presales": "auto",
    "proposal": "auto",          # drafting the proposal is auto; SENDING it is gated
    "project": "auto",
    "functional": "auto",
    "sysadmin": "auto",
    "outreach_generate": "auto",
    "log_to_odoo": "auto",
    "status_update": "auto",
    # gated
    "outreach_send": "approval",
    "proposal_send": "approval",
    "pricing_override": "approval",
    "contract_commitment": "approval",
    "code_deploy": "approval",
    "client_comms_sensitive": "approval",
}


def level(store, action: str) -> str:
    override = {}
    try:
        override = store.get_setting("autonomy") or {}
    except Exception:
        override = {}
    return override.get(action) or AUTONOMY.get(action, "auto")


def gate(store, action: str, payload: dict, requester_agent: str,
         account_id: Optional[str] = None,
         engagement_id: Optional[str] = None) -> Optional[Approval]:
    """Return None if the action may run now (auto); otherwise create and
    return a pending Approval that withholds it until a human decides."""
    if level(store, action) == "auto":
        return None
    appr = Approval(action_type=action, payload=payload, requester_agent=requester_agent,
                    account_id=account_id, engagement_id=engagement_id)
    return store.create_approval(appr)
