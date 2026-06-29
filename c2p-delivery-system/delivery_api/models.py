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
    crm_lead_id: Optional[int] = None      # linked Odoo records, once synced
    sale_order_id: Optional[int] = None
    project_id: Optional[int] = None
    created_at: str = Field(default_factory=_now)
    # Each stage's latest structured output lives here, keyed by stage name.
    stages: dict[str, Any] = Field(default_factory=dict)


class CreateEngagement(BaseModel):
    company: str
    odoo_db: Optional[str] = None


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
