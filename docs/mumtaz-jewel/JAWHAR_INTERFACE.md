# Jawhar interface and API — phase 0

Date: 11 Nov 2026. Decision by the owner: Jawhar is a **standalone product
backed by Odoo Community**. Its interface is not the Odoo web client.

## Shape

```
apps/jawhar-web          the interface: React + TypeScript (Vite), static files
        │  JSON over HTTPS, same origin, Odoo session cookie
addons/mumtaz_jewellery_api   the one door: /jawhar/v1/*, runs as the signed-in user
        │  ORM
Odoo 19 Community + mumtaz_jewellery, _vip, _owner, _sale
```

Why the API lives in Odoo rather than a separate service (roadmap §4, D8:
"Odoo-native first with clean service boundaries"): every call runs **as the
signed-in Odoo user**, so access rights and record rules apply unchanged. The
API cannot show a staff login a Royal client that the web client would hide,
and there is no second user model to keep in step. A service in front of
Odoo would need a service account and would have to reimplement that
filtering; this does not. The agents (phase 5) will come through the same
door, with their autonomy level enforced there.

Rules the tests hold (`addons/mumtaz_jewellery_api/tests/test_api.py`):

| Rule | Test |
| --- | --- |
| Unauthenticated → JSON 401, never a redirect | `test_unauthenticated_gets_json_401_not_a_redirect` |
| Figures are read, not computed; discount touches making only | `test_piece_breakdown_is_the_engine_figure` |
| The API sees what the person sees | `test_restricted_client_hidden_from_staff_visible_to_vip_manager`, `test_today_summary_counts_only_what_the_person_may_see` |
| A record you may not read is 404, not 403 (a 403 confirms it exists) | same |
| Every call is audited, failed sign-ins included; staff cannot read the audit | `test_login_wrong_password_is_401_and_audited`, `test_audit_hidden_from_staff` |

## Endpoints (v1, all read-only in phase 0)

`GET /health` · `POST /auth/login` · `POST /auth/logout` · `GET /me` ·
`GET /today` · `GET /rates/current` · `GET /rates` · `GET /pieces` ·
`GET /pieces/<id>?discount=` · `GET /clients` · `GET /clients/<id>` ·
`GET /sales/quotes` · `GET /sales/orders` · `GET /sales/orders/<id>` ·
`GET /sales/invoices` · `GET /sales/invoices/<id>` · `GET /memos` ·
`GET /old-gold` · `GET /owner/cards`

Envelope: `{"ok": true, "data": …}` or `{"ok": false, "error": {"code", "message"}}`.
Writes arrive in later phases, each with its autonomy level (A read,
B recommend, C draft, D execute with named approval, E prohibited).

## Screens (phase 0)

Sign-in · Today (rate, stock, quotes, orders, unpaid, memos, old gold,
clients, decision cards) · Decision cards · Pieces (search, karat, on-hand) ·
Piece detail with the engine's breakdown and a dealer-discount selector that
reprices server-side · Clients · Client 360 · Quotations / Orders · Order
detail with the frozen snapshot per line · Invoices · Invoice detail ·
Pieces on approval · Gold rate register · Old gold.

English and Arabic from one dictionary (`src/lib/i18n.ts`); the toggle flips
`dir` to `rtl`. Formatting is display-only (`src/lib/format.ts`): nothing in
the app computes a figure.

## Running it

Development, against a local Odoo on 8069 that has the five modules:

```bash
cd apps/jawhar-web && npm ci && npm run dev      # http://127.0.0.1:5173/app/
```

Checks: `npm run typecheck`, `npm test` (vitest), `npx vite build`.
The Odoo side runs through `scripts/jewel_ci.sh` as before (the API module is
in its install list and test tags).

Staging (`deploy/jewel-staging/deploy.sh`): the script builds the interface
in a `node:22-alpine` container (no Node on the host), publishes `dist/` to
`/opt/mumtaz/jewel-app`, and `--modules` installs any module in `MODULES`
missing from the demo database. nginx serves `/app/` from that folder and
proxies `/jawhar/` to Odoo, both behind the same allow-list / password as
the back office; `install_nginx_conf.sh` puts the server block in place with
backup, test and rollback.

## Verified, 11 Nov 2026

- API: 11 HttpCase tests, 0 failures, fresh database, five modules.
- Interface: tsc clean; 10 unit tests, 0 failures; production build 211 kB
  JS / 8.9 kB CSS; headless walk of 18 screens (both languages) against a
  seeded Odoo — every screen with content, no error box, discount reprices
  making/subtotal/VAT/total and nothing else.

## Next (in the order the owner approved)

1. Sales: quote → price from rate → confirm → invoice from the interface (writes, level D)
2. POS: counter sale, server-side pricing, rate snapshot with expiry, old gold at the till
3. CRM + outreach: pipeline, campaigns drafted by agents (level C)
4. Website option per tenant
5. Agents and automations through the same API door
