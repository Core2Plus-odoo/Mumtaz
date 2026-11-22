# Jawhar — system architecture

## 1. Layers

```
Visitors ──► Public site (static HTML, nginx)  ──► /jawhar/public/site/*  (lead capture)
Clients  ──► Kiosk / client app (React)        ──► /jawhar/public/kiosk/*, /jawhar/public/client/*
Staff    ──► Jawhar app (React, Vite)          ──► /jawhar/v1/*  (runs as the signed-in user)
Agents   ──► same /jawhar/v1 door + tool layer ──► policy (levels A–E), audit, drafts
                                                      │
                                               Odoo 19 Community
                                   mumtaz_jewellery* (13 modules) over stock/sale/account/crm/mail
                                                      │
                                               PostgreSQL (one database per tenant)
Platform ──► mumtaz_tenant_manager / branding / control_plane / routing (control-plane database)
```

## 2. Components and where they live

| Component | Code | Runtime |
| --- | --- | --- |
| Engine modules | `addons/mumtaz_jewellery*` | Odoo workers in compose project `mumtaz-jewel-staging` |
| API door | `mumtaz_jewellery_api/controllers` | same Odoo, `/jawhar/v1`, JSON over HTTP, session cookie |
| Public doors | kiosk, client, website modules | same Odoo, `/jawhar/public/*`, no session, capped |
| Jawhar app | `apps/jawhar-web` | static build at `/app/`, nginx |
| Public site | `website/jewel` | static at `/`, nginx; `site/jawhar.css` is the design system |
| Voice | ElevenLabs agent configured per tenant (`mumtaz_jewellery.voice_agent_noor`) | browser ↔ ElevenLabs; tools call the public kiosk door |
| Models | Anthropic via `mumtaz_jewellery_ai/services/provider.py`; optional | server side only; restricted data excluded |
| Platform | `addons/mumtaz_tenant_manager`, `mumtaz_branding`, `mumtaz_control_plane`, `mumtaz_portal_routing` | control-plane Odoo (not yet deployed for Jawhar) |

## 3. Data flows that matter

- **Price**: rate entered → approved by a second user → `jewellery.gold.rate.get_current` → pricing engine → `sale.order.line` fields frozen → `account.move` lines carry the rate. No client-side arithmetic; the API returns the engine's figures.
- **Sale at the counter**: `/counter/commit` → one transaction: lock the lot row, check the discount limit, apply the old-gold credit, AML gate, confirm order, deliver, invoice, register payment; any failure rolls everything back.
- **Lead from the website**: form → `/jawhar/public/site/demo-request` → validation, honeypot, per-contact cap → `jewellery.demo.request` + `crm.lead` tagged "Jawhar demo"; consent text and time stored; a person follows up.
- **Agent run**: user asks → policy decides level → tools call the same ORM as the user → draft stored with digest → person approves → action executes under the approver's name → audit row.

## 4. Environments

| Environment | Host | Branch | Notes |
| --- | --- | --- | --- |
| Local CI | container, Postgres 16 | any | `scripts/jewel_ci.sh` installs 14 modules, runs 266 tests |
| GitHub CI | Actions | PRs | lint, `check_sudo.py`, Jawhar CI, platform install CI |
| Staging | `jewel.mumtaz.digital`, compose project on the shared VPS | `jewel-staging` = `origin/main` | isolated DB and volumes; public site at `/`, app and Odoo behind basic auth |
| Production | none yet | — | needs its own host (DECISION J-07) |

## 5. Quality attributes

- Isolation: one database per tenant; record rules inside; `sudo()` labelled and CI-checked.
- Observability: API audit rows, agent run log, nginx access logs; metrics and tracing PLANNED.
- Performance: list endpoints paged; counter commit under one second on the demo DB (not benchmarked at scale: NOT VERIFIED).
- Availability: single VPS; no HA; backups via `deploy/jewel-staging/backup.sh` (restore drill NOT VERIFIED).

## 6. Target evolution (Phases 3–8)

Event bus on `base_automation` + a `jewellery.event` table; command centre reading from it; tenant console in the Jawhar app talking to the control plane through a signed service door; brand tokens served to the app at login; per-tenant model keys stored encrypted; a separate production host with the control plane on its own database.
