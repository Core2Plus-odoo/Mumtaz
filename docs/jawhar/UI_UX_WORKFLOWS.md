# Jawhar — UI/UX workflows

Statuses refer to the Jawhar React app unless noted.

## 1. Staff (associate, manager)

| Flow | Screens | Status |
| --- | --- | --- |
| Morning: approve the rate | Rates → approve (second person) → Today shows the rate | VERIFIED |
| Serve a client at the counter | Counter → find client → scan/enter serial → price → old gold → discount → AML check → pay → receipt | VERIFIED |
| Build and send a tray | Clients → Tray builder → add pieces → link with expiry → client opens public tray → viewing request → reservation | VERIFIED |
| Outreach for an occasion | Outreach → draft (Layla) → consent check → person sends from own phone → log | VERIFIED |
| Memo out / back | Memos → issue → stock moves → return | VERIFIED |
| Transfer between stores | Stores → transfer → transit → receive → reconcile grams | VERIFIED |
| Import a stock book | Pieces → Import → preview errors → apply | VERIFIED |
| Kiosk request follow-up | Kiosk → confirm/decline → opportunity + priced draft | VERIFIED |
| Approve an agent draft | Agents → approvals inbox → compare digest → approve | VERIFIED |

## 2. Owner

Today (worklist, approvals, cards), Stores (grams, exposure), Rates
history, Compliance. Command centre with lineage (why this number, which
store, which rate) is Phase 3: PLANNED.

## 3. Client

Kiosk: greet → browse shelf at the approved rate → try on (camera, fit
estimate) → ask Noor → request viewing or next-day delivery (name, phone) →
reference. Client app: one-time code → tray, what she owns, consent. Public
tray link: view, ask to see, never reserve. VERIFIED with fake camera; live
voice and real device NOT VERIFIED.

## 4. Tenant administrator (Phase 4, PLANNED)

Onboarding: company, country, currency, stores → users and roles → brand
(logo, colours, product name) → rate source → agents on/off and autonomy →
import stock book → go live checklist. Settings: plan and usage, data
export, offboarding request.

## 5. Platform / reseller operator (existing control plane, PARTIALLY)

Create tenant (bundle `jawhar`), assign brand, plan and domain; see usage and
billing; impersonate for support (time-boxed, logged) PLANNED.

## 6. Visitor (public site, delivered)

Land → read a truthful status → see screens → request a demo (consent) →
receive a reference → a person follows up.

## 7. Design debt in the app (for Phase 2b)

Palette migration to the v2 tokens; density on Today; company/store switcher
in the shell; empty states; kiosk theme unification; dark mode.
