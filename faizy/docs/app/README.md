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
403 `signup_closed`, 409 `already_registered`.

- Shipped off. A Manager sets system parameter `faizy.app_signup` to `on`.
- An email or phone already on file is refused, never attached: the caller
  gets a login, so matching an existing customer by phone would hand their
  family and orders to anyone who knows the number.
- Creates a portal user only. No subscription and no family member; the
  customer adds family afterwards and the plan gate applies as on the web.

## Open gaps before the app goes public

- A1 Passwordless login by WhatsApp code (OB-03). Needs the WhatsApp provider.
- A2 Money figures in the API (`amount_total`, fees, activity counts) are not
  yet checked against `faizy.show_plan_prices`. No app screen may show them
  until that is audited.
- A3 API versioning. A4 cookie vs token for the app session.
- A5 Rate limiting / CAPTCHA and proof of email or number ownership on
  sign-up. Do not switch `faizy.app_signup` on for the public before this.
- A6 Push notifications.
- Voice assistant (ElevenLabs): not built. It may read, answer and fill in a
  request; only the customer's tap sends it.
