# FAIZY customer app: ERP side

The customer app (React Native, ADR-013) has no backend of its own. It reads
and writes the FAIZY Odoo ERP through the JSON routes in
`faizy_website/controllers/api.py`. A customer created in the app is a
`res.partner` plus a portal `res.users` in the ERP; a request sent from the
app is a `faizy.order`.

## Routes

| Route | Auth | Purpose |
|---|---|---|
| `POST /web/session/authenticate` | none | Odoo's own login (email + password) |
| `POST /api/care/signup` | none | Create customer + portal login. Off by default |
| `GET /api/care/home` | session | Customer, family, subscription, recent orders |
| `GET /api/care/orders`, `/orders/<id>` | session | Requests and their status / reviewed evidence |
| `GET /api/care/request/options` | session | Services and family members for a new request |
| `POST /api/care/request` | session | Create a request (402 `needs_plan` when a plan is required) |

## Sign-up (`POST /api/care/signup`)

Body: `name`, `phone`, `email`, `password` (8+ characters), optional
`country_code`. Responses: 200 `{ok, partner}`, 400 `{errors}`,
403 `signup_closed`, 409 `already_registered`, 429 `too_many_attempts`.

- Shipped off. A Manager sets system parameter `faizy.app_signup` to `on`.
- An email or phone already on file is refused, never attached: the caller
  gets a login, so matching an existing customer by phone would hand their
  family and orders to anyone who knows the number.
- Rate limited: 5 attempts per caller address per hour and 60 from all
  callers per hour, refused attempts included (`faizy.api.throttle`). The
  per-address limit needs Odoo `proxy_mode` on and nginx forwarding
  `X-Forwarded-For`; otherwise every caller shares one address.
- Creates a portal user only. No subscription and no family member; the
  customer adds family afterwards and the plan gate applies as on the web.

## Open gaps before the app goes public

- A1 Passwordless login by WhatsApp code (OB-03). Needs the WhatsApp provider.
- A2 Audited 28 Nov 2026: the service catalogue carries no price fields
  (tested). Order amounts and activity counts go only to the logged-in
  customer for their own account, as the web portal already shows them.
  Whether the app shows them is Umer's decision (D3).
- A3 API versioning. A4 cookie vs token for the app session.
- A5 Rate limiting is in. Still missing: proof of email or number ownership,
  and confirmation of the proxy setting on production. Do not switch
  `faizy.app_signup` on for the public before both.
- A6 Push notifications.
- Voice assistant (ElevenLabs): not built. It may read, answer and fill in a
  request; only the customer's tap sends it.
