# Mumtaz Jewel: working rules (read before any change)

These rules apply to everything under `addons/mumtaz_jewellery*`, `docs/mumtaz-jewel/` and any Mumtaz Jewel deploy files. Where they conflict with the repo-root `CLAUDE.md` ("commit to `main`", "deploys go to `main`"), **these win for Mumtaz Jewel work.**

## Branching and deploys
- Work only on `claude/mumtaz-jewellery-phase2` (or a branch cut from it). Never commit or push to `main`: `main` auto-deploys to the production VPS.
- Open a pull request; a human merges. No deploy, restart or config change on any server without a named human approval in the chat.
- `jewel.mumtaz.digital` is a staging/demo host until the owner says otherwise. It must not share a database, volume or `.env` with the live C2P CRM or any production tenant.

## Data and secrets
- Synthetic data only. No real client names, customer data, keys or tokens in code, logs, tests or docs. Secrets come from environment variables.
- Never send a message to a real person or run a real payment from a script, agent or test.
- Compliance values (VAT, retention, AML thresholds) are configuration for the named finance manager to confirm; do not invent rules.

## Product rules
- Odoo 19 Community only. No Enterprise code. Prices come only from the approved gold rate and the pricing engine; an AI never produces a number.
- Autonomy levels: A read, B recommend, C draft, D execute with named approval, E prohibited. Restricted VIP data never enters a model request.
- Extend existing addons (`mumtaz_jewellery`, `_vip`, `_owner`); do not duplicate stock, customer or finance records.

## Definition of done for any change
1. Code, plus an Odoo `TransactionCase` test where behaviour changed.
2. Run the real test suite and report the actual result (pass/fail counts), not an assumption.
3. Update `docs/mumtaz-jewel/` (roadmap status, feature gap row) in the same pull request.
4. Stop and ask before: deleting functionality, destructive migrations, replacing the pricing engine, changing authentication or tenant isolation, changing production infrastructure, deploying.

## Where things are
Roadmap `IMPLEMENTATION_ROADMAP.md` · decisions `ARCHITECTURE.md` · gaps `FEATURE_GAP_ANALYSIS.md` · product direction `BLUEPRINT_V2_RECONCILIATION.md` · operating cycle doc (Claude Docs, linked from the roadmap).
