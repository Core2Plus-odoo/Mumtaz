# Jawhar — API and integration design

## 1. The door (`/jawhar/v1`, `mumtaz_jewellery_api`)

- Runs as the signed-in Odoo user. Access rights and record rules apply as in the web client; a restricted client is 404.
- JSON responses `{ok, data}` or `{ok:false, error:{code,message}}`; figures come from the engine; every call writes an audit row.
- 64 routes today: auth, rate, pieces (+import), clients (+consent, occasions, memos), owner cards, quotes/orders/invoices/payments, counter, pipeline/trays, outreach, stores/transfers/reconciliation, channels, compliance, documents, kiosk requests, agents (runs, drafts, approvals).
- Versioning: path version; additive changes only within v1; a breaking change opens v2 beside v1.

## 2. Public doors (`/jawhar/public/*`)

| Prefix | Module | Writes | Protection |
| --- | --- | --- | --- |
| `/kiosk` | kiosk | one request per interaction | per-phone daily cap, no ids, serials only |
| `/client` | client | consent, tray reply | one-time code (3/hour), token header |
| `/site` | website (new) | demo request | honeypot, per-contact daily cap, nginx `limit_req` 6/min per address, consent required |

Public doors return no internal ids and no other client's data. On staging
only `/jawhar/public/site/` is reachable without the demo password (nginx
`^~` location, pending apply: see `DEPLOYMENT_RUNBOOK.md`).

## 3. Agent tool layer

Agents call the same ORM under the user's rights through a fixed tool list
per agent (`policy.py`). Each tool declares its autonomy level; drafts carry a
digest that the approval must match. Models receive a grounded context from
which restricted fields are removed before the request is built.

## 4. External systems

| System | Direction | Today | Rule |
| --- | --- | --- | --- |
| ElevenLabs (voice) | browser ↔ provider; tools → kiosk door | configured per tenant; two client tools to register | the agent never prices; it reads the shelf |
| Anthropic (models) | server → provider | optional; key per deployment | no restricted data; no numbers produced |
| Gold rate feed | provider → draft rate | HTTPS adapter, draft only | a person approves |
| Stripe | control plane | platform billing | webhooks idempotent by event id (to test) |
| ZATCA / FBR e-invoicing | Odoo → authority | platform modules exist for other products | per tenant, after localisation decision |
| WhatsApp Business | out | none | only when an account exists; consent per channel |
| Card terminals | counter | none | decision pending |

## 5. Webhooks and events (Phase 6)

A `jewellery.event` table written by business methods (rate approved, sale
committed, transfer received, threshold crossed); `base_automation` rules
and the command centre read it; outbound webhooks per tenant with HMAC
signature and retry; idempotency key on every inbound hook.

## 6. Error and rate-limit conventions

400 validation, 401 no session, 403 forbidden action, 404 not found or not
visible, 409 conflict (piece already sold), 429 cap reached; message text is
written for the person who sees it, in the request's language where the
module has the string.
