# Jawhar — AI agent architecture

## 1. What exists (VERIFIED)

- `mumtaz_jewellery_ai`: `jewellery.ai.agent` with runs, tool calls, drafts, approvals inbox, audit; `policy.py` defines agents **Zayan** (owner's analyst and product guide) and **Layla** (clienteling) with per-tool autonomy levels; `services/provider.py` wraps the model provider, optional.
- `mumtaz_jewellery_kiosk`: **Noor**, the client-facing kiosk agent (ElevenLabs voice in the browser; tools read the shelf and the rate and create one request; try-on runs on device).
- Invariants enforced in code and tests: no number produced by a model; restricted VIP data stripped before any model request; drafts bound to a digest; level D actions execute under the approver's name; every run logged.
- Rayan (stock/procurement) and Amara (finance/compliance): PROTOTYPE (portrait and copy, no code).

## 2. Autonomy levels (policy, unchanged)

A read · B recommend · C draft · D execute with named approval · E prohibited. Each tool carries its level; a tenant may lower, never raise, a level (per-tenant configuration PLANNED).

## 3. Target architecture (Phases 5–7)

```
Request (user / schedule / event)
  → Orchestrator: pick agent, load role prompt, build grounded context (tenant rules, rate, scoped records; restricted fields removed)
  → Model call (per-tenant key, provider abstraction, prompt cache)
  → Tool calls through the same ORM as the user (levels enforced here)
  → Draft / recommendation / executed action
  → Approval (digest-bound) → execution under approver's name
  → Audit row + evaluation sample
```

Additions: an orchestrator service in `mumtaz_jewellery_ai/services/orchestrator.py`; scheduled agent jobs via `ir.cron` (morning brief, reconciliation anomalies); event-triggered runs from the `jewellery.event` bus; per-tenant agent settings (on/off, level ceiling, language, voice id, model key encrypted); an evaluation corpus with expected tool calls per scenario, run in CI against a recorded provider.

## 4. Agent roster and role prompts (to write in Phase 5)

| Agent | Role | Reads | May draft | Needs approval | Never |
| --- | --- | --- | --- | --- | --- |
| Zayan | owner's analyst, product guide | cards, stores, rates, pipeline | briefs, questions to managers | nothing executes | prices |
| Layla | clienteling | client files (not restricted unless named), occasions, trays | outreach, tray suggestions | sending (by a person) | contact without consent |
| Noor | kiosk | shelf, rate | viewing/delivery request | confirmation (person) | reservations, prices beyond the engine |
| Rayan | stock & procurement | pieces, grams, transfers, purchase | replenishment suggestions, transfer proposals | transfers, purchase orders | moving stock |
| Amara | finance & compliance | invoices, AML flags, reconciliation | exception reports, KYC reminders | nothing executes | thresholds, postings |

## 5. Guardrails

Grounding: every answer cites the record or figure it used; tool outputs are the only source of numbers. Scope: tools accept ids the user can already read. Privacy: `restricted` records excluded unless the user is named on them, and then only non-sensitive fields enter the prompt. Cost: per-tenant budget and run cap PLANNED. Evaluation: golden set per agent, regression in CI, human review sample weekly PLANNED.

## 6. Voice

ElevenLabs agent per tenant; two client tools (`kiosk_try_on`, `kiosk_tryon_fit`) still to register in the console (user action); live-voice verification on a device outstanding.
