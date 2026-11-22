# Faizy — Entity Relationship Reference

The real schema: every model that exists in `faizy_core`, `faizy_website` and `faizy_ai` today (22
models total, confirmed by `odoo/tools/validate_modules.py`), not an illustrative generic ERP
shape. `res.partner`, `res.company` and `account.move` are native Odoo models, extended rather than
duplicated.

```mermaid
erDiagram
    COMPANY ||--o{ ORDER : "configures rates for"
    COMPANY ||--|| WHATSAPP_PROVIDER_CONFIG : "holds (same record)"

    PARTNER ||--o{ FAMILY_MEMBER : "has"
    PARTNER ||--o{ ORDER : "requests"
    PARTNER ||--o| SUBSCRIPTION : "current (computed)"
    PARTNER ||--o{ SUBSCRIPTION : "history"
    PARTNER ||--o{ DOCUMENT : "files"
    PARTNER ||--o{ BRIDGE_REQUEST : "asks"
    PARTNER ||--o{ PRODUCT_REQUEST : "asks"
    PARTNER ||--o{ WALLET_TXN : "owns"
    PARTNER ||--o{ WHATSAPP_MESSAGE : "receives"
    PARTNER ||--o| VENDOR_FIELDS : "extends (is_faizy_vendor)"

    FAMILY_MEMBER ||--o{ ORDER : "for (optional)"
    FAMILY_MEMBER ||--o{ DOCUMENT : "owns"
    FAMILY_MEMBER ||--o{ BRIDGE_REQUEST : "for"
    FAMILY_MEMBER ||--o{ PRODUCT_REQUEST : "for"

    SERVICE_CATEGORY ||--o{ SERVICE : "groups"
    SERVICE ||--o{ ORDER : "fulfilled as"
    SERVICE }o--o{ WORKER : "worker can do"
    SERVICE }o--o{ APPLICATION : "applicant can do"

    AREA }o--o{ WORKER : "covers"
    AREA }o--o{ APPLICATION : "covers"

    WORKER ||--o{ ORDER : "assigned to"
    WORKER ||--o{ WALLET_TXN : "earns"
    WORKER ||--o{ WHATSAPP_MESSAGE : "receives"
    APPLICATION ||--o| WORKER : "becomes, on approval"

    VENDOR_FIELDS ||--o{ ORDER : "fulfils (vendor_id)"

    PLAN ||--o{ PLAN_PRICE : "priced per currency"
    PLAN ||--o{ PLAN_FEATURE : "describes"
    PLAN ||--o{ SUBSCRIPTION : "subscribed as"

    SUBSCRIPTION ||--o{ ACTIVITY_LOG : "meters usage via"
    SUBSCRIPTION }o--o{ ACCOUNT_MOVE : "invoiced as (native)"
    ORDER ||--o| ACTIVITY_LOG : "consumes activity, logged as"

    ORDER ||--o{ WHATSAPP_MESSAGE : "triggers (per transition)"
    ORDER ||--o| AI_DRAFT : "may originate from"
    ORDER ||--o{ AI_DRAFT : "may be updated by"
    ORDER ||--o| BRIDGE_REQUEST : "results from (optional)"
    ORDER ||--o| PRODUCT_REQUEST : "results from (optional)"
    ORDER ||--o{ WALLET_TXN : "may generate"
    ORDER ||--o{ ORDER : "recurs as (parent_order_id)"

    AI_AGENT ||--o{ AI_DRAFT : "drafts"
    AI_DRAFT ||--o| WHATSAPP_MESSAGE : "queues, once executed"
    AI_DRAFT ||--o| ORDER : "creates/updates, once executed"
    AI_INBOUND }o--o| PARTNER : "matched to, by phone"
    AI_INBOUND }o--o| ORDER : "may reference"
```

## Field-level notes that matter more than the diagram shapes

- **`faizy.order` is the hub of the whole system.** Every other transactional model either produces
  an order (`bridge.request`, `product.request`, recurring template via `parent_order_id`) or reacts
  to one (`whatsapp.message`, `ai.draft`, `activity.log`, `wallet.transaction`). There is no
  generic "transaction" superclass — `faizy.order` plays the role a blueprint-style ERP would split
  across `SalesOrder` + `ServiceOrder` + `WorkOrder`.
- **`faizy.subscription` → `account.move` is a plain `Many2many`, not a line-level allocation
  table.** The blueprint's generic model (§7.3) calls for `Invoice <-> Payment` via settlement
  allocations with residual/FX tracking; Faizy relies entirely on native `account.move` payment-state
  tracking instead of a Faizy-specific allocation model. That is a reasonable simplification given
  there is exactly one invoice per billing period, not a many-to-many billing scenario.
- **`faizy.wallet.transaction` has no relationship to `account.move` at all.** It is a parallel,
  informational ledger (`txn_type`, `amount`, `partner_id`/`worker_id`), not a subledger that
  reconciles to anything. Treat its balance as directional information for the customer-facing UI,
  not as an accounting fact — this is already implicit in the code (no journal posting anywhere
  near it) but is easy to misread from the model name alone, hence calling it out here.
- **`faizy.ai.draft.order_id` and `result_order_id` are deliberately different fields** — the first
  is the order a draft is *about* (for `order_update`), the second is the order a draft *created*
  (for `order_create`). Collapsing them into one field would make an executed `order_create` draft
  indistinguishable from an `order_update` draft about a pre-existing order.
- **No field anywhere stores a currency-converted total across currencies.** `faizy.plan.price` is
  one row per currency (no FX computation); `faizy.order.currency_id` defaults to
  `env.company.currency_id` and never converts. This matches ADR-006/PLT-05's narrow scope (multi
  *market pricing*, not multi-currency accounting) — correct for "publish a real local price per
  market" but would not survive a requirement to report consolidated revenue across currencies
  without a conversion step that does not exist today.

## Referential rules actually enforced in code (not aspirational)

- `faizy.order._check_vendor_approved`: a `vendor_id` must be an active, approved Faizy vendor —
  enforced as a model constraint, not just a UI domain (the code comment explains exactly why: "a
  domain is advisory... it does nothing against an import, an automation or a write from code").
- `faizy.ai.draft._check_content`: blocks stale WhatsApp numbers and disallowed order actions from
  ever reaching a queued message — a real server-side guard, not a UI validation.
- `faizy.ai.draft.write`: a non-approver can only edit `AI_DRAFT_FIELDS` on their own still-`draft`
  rows — enforced in `write()`, so it holds against direct ORM calls too, not only the form view.
- No `ondelete='cascade'` was found on any fiscally-relevant relationship in `faizy_order.py` or
  `faizy_subscription.py` (child orders use `ondelete="set null"` on `parent_order_id`) — consistent
  with the blueprint's "never cascade-delete posted fiscal or inventory history" invariant, though
  this project has no posted-history concept to begin with (ADR-011).
