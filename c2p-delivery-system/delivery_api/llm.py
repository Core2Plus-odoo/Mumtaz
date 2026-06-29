"""Model-abstraction layer — the one place that talks to a model.

Knowledge & Independence (cross-cutting, built from Phase 1):
  * Provider and model are CONFIG, not hardcoded. No other file names a model.
    Swapping the model is a one-line env change.
  * Per-task routing: C2P_MODEL_<TASK> overrides the default for that agent
    (e.g. a cheap model for simple stages, a strong one for developer).
  * Every call is logged as owned, labelled data (agent_runs) so C2P keeps the
    dataset that gives future optionality — cheaper models, self-hosting, evals.

Today this points at Anthropic (Claude). To swap providers, implement another
branch in `_complete` and set C2P_LLM_PROVIDER.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

_log = logging.getLogger("c2p.llm")

PROVIDER = os.getenv("C2P_LLM_PROVIDER", "anthropic")
DEFAULT_MODEL = os.getenv("C2P_MODEL", "claude-sonnet-4-6")
# Web search is Anthropic's server-side tool; off-switch for accounts/models
# that don't have it enabled (the agent then reasons without live grounding).
WEB_SEARCH_ENABLED = os.getenv("C2P_WEB_SEARCH", "1") == "1"

_client = None
_clients_by_key: dict = {}


class LLMError(Exception):
    """Raised for provider/transport failures (mapped to HTTP 502 upstream)."""


def _tenant_key() -> Optional[str]:
    """The current tenant's own Anthropic key, if multi-tenant context set one."""
    try:
        import tenancy
        return tenancy.current_secret("anthropic_key")
    except Exception:
        return None


def _anthropic():
    """Default client (env key) — or the current tenant's own key when present,
    so each tenant bills against and isolates their own model account."""
    from anthropic import Anthropic
    key = _tenant_key()
    if key:
        if key not in _clients_by_key:
            _clients_by_key[key] = Anthropic(api_key=key)
        return _clients_by_key[key]
    global _client
    if _client is None:
        _client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    return _client


def model_for(task: str) -> str:
    """Per-task model routing via env, falling back to the default model."""
    return os.getenv(f"C2P_MODEL_{task.upper()}", DEFAULT_MODEL)


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of the reply, tolerating ```json fences and
    stray prose by slicing between the first '{' and the last '}'."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON object in model response")
    return json.loads(t[a:b + 1])


def _complete(task: str, system: str, user: str, max_tokens: int,
              web_search: bool) -> dict:
    """Provider-agnostic single completion. Returns text + usage metadata."""
    model = model_for(task)
    if PROVIDER != "anthropic":
        raise LLMError(f"Unsupported C2P_LLM_PROVIDER '{PROVIDER}'")

    kwargs: dict[str, Any] = dict(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    if web_search and WEB_SEARCH_ENABLED:
        kwargs["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }]

    resp = _anthropic().messages.create(**kwargs)
    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()
    usage = getattr(resp, "usage", None)
    return {
        "text": text,
        "model": model,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def run_json(task: str, system: str, user: str, max_tokens: int = 2048,
             web_search: bool = False, store=None,
             account_id: Optional[str] = None,
             engagement_id: Optional[str] = None) -> dict:
    """Run an agent, return parsed JSON, and log the run as owned data.

    Raises on transport failure or unparseable output; the caller maps that to
    an HTTP error. The run is logged either way (errors included) so the
    dataset captures failures too.
    """
    t0 = time.time()
    meta: dict = {}
    out: Optional[dict] = None
    err: Optional[str] = None
    try:
        meta = _complete(task, system, user, max_tokens, web_search)
        try:
            out = _extract_json(meta["text"])
        except (ValueError, json.JSONDecodeError):
            # Self-heal: one strict retry with more room (covers a truncated or
            # prose-wrapped first reply).
            meta = _complete(
                task, system,
                user + "\n\nIMPORTANT: Return ONLY one complete, valid JSON "
                       "object — no prose, no markdown fences, not truncated.",
                min(max(max_tokens, 4096) * 2, 8192), web_search)
            out = _extract_json(meta["text"])
        return out
    except Exception as exc:  # noqa: BLE001 - logged below, re-raised
        err = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if store is not None and hasattr(store, "log_run"):
            try:
                store.log_run({
                    "task": task,
                    "model": meta.get("model") or model_for(task),
                    "account_id": account_id,
                    "engagement_id": engagement_id,
                    "system": system,
                    "input": user,
                    "output": out,
                    "raw_text": meta.get("text"),
                    "input_tokens": meta.get("input_tokens"),
                    "output_tokens": meta.get("output_tokens"),
                    "ms": int((time.time() - t0) * 1000),
                    "error": err,
                })
            except Exception:  # noqa: BLE001 - logging must never break a call
                _log.exception("agent_run logging failed for task=%s", task)
