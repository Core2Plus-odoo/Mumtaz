# Jawhar — SaaS product blueprint

## 1. Definition

Jawhar is a jewellery retail operating system sold as a service to boutiques,
chains and groups in the GCC and Pakistan, and offered white-labelled to
resellers and groups who want it under their own name. Engine: Odoo 19
Community with Jawhar modules. Interface: the Jawhar React application, the
public kiosk and the client app. Intelligence: governed agents through the
same API door as people.

Positioning: the trade-specific layer that Odoo lacks (approved gold rate,
gram-level stock, private clienteling, counter in one transaction, AML at the
till) with the back office Odoo already does well (accounting, purchase,
inventory, HR when wanted).

## 2. Personas

| Persona | Needs | Surfaces |
| --- | --- | --- |
| Owner / group principal | Today's position, decisions with evidence, margins by store, exposure to the rate | Today, owner cards, Stores, Rates; command centre (Phase 3) |
| Store manager | Rate approval, approvals inbox, reconciliation, staff limits | Today, Rates, Stores, Compliance |
| Sales associate | Client file at the counter, tray, quote to invoice, memos | Counter, Clients, Tray, Quotes |
| Relationship manager (VIP) | Restricted records, occasions, outreach drafts, consent | Clients, Outreach, Memos |
| Finance / compliance | AML thresholds, KYC, frozen rate on documents, VAT | Compliance, Invoices, Odoo Accounting |
| Stock controller | Pieces, import, transfers, counts | Pieces, Stores, Odoo Inventory |
| Client | Her tray, what she owns, her consent, the kiosk | Client app, kiosk, tray link |
| Tenant administrator | Users, stores, branding, plan, data export | Tenant console (Phase 4) |
| Platform / reseller operator | Provision, bill, brand, support, observe | Control plane (existing `mumtaz_control_plane`, to be extended) |

## 3. Editions (proposal, prices not set)

| Edition | For | Included |
| --- | --- | --- |
| Boutique | 1–2 stores | Core, Counter, Client book, Pieces, Rates, Compliance fields, Zayan |
| Chain | 3–20 stores | + Stores & transfers, Sales Hub, Outreach, Channels, Client app, Layla, Noor kiosk |
| Group / White-label | groups and resellers | + brand, custom domain, multi-company, tenant console, reseller margin, SLA |

Agents are metered per run and sold as add-ons per the intelligence page's
proposed shape; nothing is billable until `DECISION_REGISTER.md` J-05 is taken.

## 4. Module catalogue (commercial names → code)

See `ODOO_MODULE_MAP.md`. Commercial grouping: Core (rate, pricing, pieces,
old gold), Counter, Client book (VIP, memos, occasions), Sales Hub (CRM,
tray), Outreach, Stores, Compliance (AML/KYC), Channels, Client app, Kiosk
(Noor), Intelligence (AI), API, Website door.

## 5. Value promises (each traceable to a test)

1. No price without an approved rate; the rate used is on every document.
2. One sale is one transaction: piece, credit, discount, AML, payment, invoice.
3. Private clients are invisible to the unnamed and every look is logged.
4. Agents draft, people send; restricted data never leaves the tenant for a model.
5. Every store closes on fine grams, every transfer has two sides.

## 6. Revenue model shape

Subscription per store per month by edition; agent usage metered; onboarding
and data migration as services; reseller discount from list; white-label
fee. The control plane already models plans, features, subscriptions and
usage metrics; prices are configuration, entered when approved.

## 7. Non-goals for the next two phases

Public e-commerce beyond shelf publication; card-terminal integration;
payroll; manufacturing routing; WhatsApp sending (until a Business account
exists); Enterprise features (Studio, Documents, Sign, IoT).
