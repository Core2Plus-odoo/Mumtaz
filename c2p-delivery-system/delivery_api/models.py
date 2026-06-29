"""Data models for the C2P delivery system.

An Engagement is the spine that threads the five stages. Each stage writes its
JSON output back onto the engagement so the next stage can read it. The store is
in-memory here; swap `STORE` for a database or Odoo-backed persistence later.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

STAGES = ["presales", "proposal", "project", "functional", "developer"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Engagement(BaseModel):
    id: str = Field(default_factory=lambda: "eng_" + uuid.uuid4().hex[:12])
    company: str
    odoo_db: Optional[str] = None          # which tenant DB this engagement targets
    account_id: Optional[str] = None       # the Account this engagement belongs to
    crm_lead_id: Optional[int] = None      # linked Odoo records, once synced
    sale_order_id: Optional[int] = None
    project_id: Optional[int] = None
    created_at: str = Field(default_factory=_now)
    # Each stage's latest structured output lives here, keyed by stage name.
    stages: dict[str, Any] = Field(default_factory=dict)


class CreateEngagement(BaseModel):
    company: str
    odoo_db: Optional[str] = None
    account_id: Optional[str] = None


# ── Phase 1: Accounts + client knowledge ──────────────────────────────────
class Account(BaseModel):
    """A client, 1:1 with an Odoo partner. Owns the knowledge base that every
    client-touching agent reads before acting and writes back to after."""
    id: str = Field(default_factory=lambda: "acc_" + uuid.uuid4().hex[:12])
    name: str
    partner_id: Optional[int] = None       # Odoo res.partner id (system of record)
    odoo_db: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    profile: dict[str, Any] = Field(default_factory=dict)


class CreateAccount(BaseModel):
    name: str
    odoo_db: Optional[str] = None
    partner_id: Optional[int] = None
    industry: Optional[str] = None
    country: Optional[str] = None


class KnowledgeEntry(BaseModel):
    """One owned, labelled fact about an account. `content` may be text or a
    structured dict. `kind` keeps entries retrievable by topic."""
    id: str = Field(default_factory=lambda: "kn_" + uuid.uuid4().hex[:12])
    account_id: str
    kind: str = "learning"                 # company_profile|stakeholder|requirement|
                                           # decision|risk|research_dossier|communication|learning
    title: str = ""
    content: Any = ""
    learned_by: str = "human"              # agent name or 'human'
    created_at: str = Field(default_factory=_now)
    tags: list[str] = Field(default_factory=list)


class KnowledgeIn(BaseModel):
    kind: str = "learning"
    title: str = ""
    content: Any = ""
    learned_by: str = "human"
    tags: list[str] = Field(default_factory=list)


class ProspectIn(BaseModel):
    """ICP definition for the Prospector agent."""
    icp: Optional[str] = Field(None, description="Free-text ICP override")
    industry: Optional[str] = None
    country: Optional[str] = "UAE"
    size_band: Optional[str] = None
    signals: Optional[str] = Field(None, description="Buying signals to look for")
    exclude: list[str] = Field(default_factory=list)
    max_results: int = 10


class ResearchIn(BaseModel):
    """Deep-research request for the Researcher agent (writes a dossier)."""
    company: Optional[str] = None          # defaults to the account name
    focus: Optional[str] = None
    web_search: Optional[bool] = None      # override the global default


# ── Phase 2: Approvals + outreach ─────────────────────────────────────────
class Approval(BaseModel):
    """A gated action waiting on a human. The decision (approve/edit/reject),
    the reason, and any human edit to the payload are captured as owned data —
    the most valuable correction signal C2P keeps."""
    id: str = Field(default_factory=lambda: "apr_" + uuid.uuid4().hex[:12])
    action_type: str                       # e.g. outreach_send, proposal_send
    payload: dict[str, Any] = Field(default_factory=dict)
    requester_agent: str = ""
    account_id: Optional[str] = None
    engagement_id: Optional[str] = None
    status: str = "pending"                # pending | approved | rejected | edited
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    reason: Optional[str] = None
    result: Optional[dict] = None          # what executing the action produced
    created_at: str = Field(default_factory=_now)


class ApprovalDecisionIn(BaseModel):
    decision: str                          # approved | rejected | edited
    reason: Optional[str] = None
    edited_payload: Optional[dict] = None  # the human's correction (owned data)
    decided_by: str = "owner"


class OutreachIn(BaseModel):
    contact_name: Optional[str] = None
    channel: str = "email"                 # email | whatsapp | linkedin
    angle: Optional[str] = None
    auto_queue_send: bool = True           # also create the gated send approval


class InfraIn(BaseModel):
    """Inputs for the System Administrator (Infrastructure Advisor) agent."""
    account_id: Optional[str] = None
    company: Optional[str] = None
    users: Optional[int] = None
    budget_band: Optional[str] = None      # lean | mid | enterprise
    data_residency: Optional[str] = None   # e.g. "UAE", "KSA (ZATCA)", "none"
    in_house_it: Optional[bool] = None
    customization: Optional[str] = None    # none | config | studio | custom modules
    integrations: Optional[str] = None
    uptime_need: Optional[str] = None      # standard | high
    compliance: Optional[str] = None
    notes: Optional[str] = None


class PresalesIn(BaseModel):
    notes: str = Field(..., description="Raw discovery notes / call summary / lead context")
    country: Optional[str] = "UAE"
    industry: Optional[str] = None


class ProposalIn(BaseModel):
    # Optional overrides; if omitted, the agent reads the stored presales output.
    instructions: Optional[str] = Field(None, description="Any extra scoping direction")


class ProjectIn(BaseModel):
    instructions: Optional[str] = None


class FunctionalIn(BaseModel):
    requirement: str
    odoo_version: str = "v17"
    country: str = "UAE"
    industry: Optional[str] = None
    installed_modules: Optional[str] = None  # free text or auto-filled from Odoo


class DeveloperIn(BaseModel):
    # If spec is omitted, the backend uses the latest functional output on the engagement.
    spec: Optional[str] = None
    target_version: str = "17"
    module_name: Optional[str] = None
    category: Optional[str] = None
    include_tests: bool = False


# In-memory engagement store. Replace with real persistence in production.
STORE: dict[str, Engagement] = {}
