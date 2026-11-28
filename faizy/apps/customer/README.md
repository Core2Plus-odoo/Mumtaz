# FAIZY customer app

React Native (Expo) app for FAIZY customers (ADR-013). It has no backend of
its own: every screen reads and writes the FAIZY Odoo ERP through
`/api/care/*` (see `faizy/docs/app/README.md`).

## Status (28 Nov 2026)

Skeleton. Not run on a phone, not built for a store, not pointed at production.

Works against a local ERP: create account, sign in, home, new request
(pick service, for whom, city, details, review, send), my requests, request
detail with reviewed evidence only, family list, WhatsApp links, sign out.
English, Urdu and Roman Urdu. Urdu wording is a draft pending review.

Not built yet: the speaking assistant (the Talk screen is a placeholder),
remembering the language and session after the app is closed, Poppins font,
push notifications, adding a family member in the app (WhatsApp link today),
translated service names and statuses (the ERP sends English).

## Run

```bash
npm install
EXPO_PUBLIC_API_BASE=http://<erp-host>:8069 EXPO_PUBLIC_ODOO_DB=<db> npm start
```

There is no production default; a build must name its server and database.

## Checks

```bash
npm run typecheck
# end-to-end against a local ERP with faizy.app_signup = on, synthetic data only
API_BASE=http://127.0.0.1:8079 ODOO_DB=<local db> npm run smoke
```

`scripts/api-smoke.ts` refuses any server that is not local unless
`ALLOW_REMOTE=staging` is set. Never run it against production.

## Rules the app keeps

- A request is created only when the customer taps Send request.
- No prices, plan numbers or statistics on any screen.
- Evidence is shown only after FAIZY has reviewed it.
- The real FAIZY logo only (`assets/faizy-logo.png`).
