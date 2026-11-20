# Core ERP Entity Relationship Reference

Illustrative, framework-independent relationships. `BillingAllocation`, `FulfillmentAllocation`, and `PaymentAllocation` are explicit linkage concepts; in Odoo these may already be represented by native relationships and should **not** be duplicated blindly. Physical schema must follow the approved platform and documented mapping.

```mermaid
erDiagram
    COMPANY ||--o{ BRANCH : has
    COMPANY ||--o{ SALES_ORDER : owns
    COMPANY ||--o{ PURCHASE_ORDER : owns
    COMPANY ||--o{ JOURNAL_ENTRY : owns
    PARTY ||--o{ SALES_ORDER : customer
    PARTY ||--o{ PURCHASE_ORDER : supplier
    SALES_ORDER ||--|{ SALES_ORDER_LINE : contains
    ITEM ||--o{ SALES_ORDER_LINE : ordered
    SALES_ORDER_LINE ||--o{ FULFILLMENT_ALLOCATION : fulfilled_by
    STOCK_MOVE ||--o{ FULFILLMENT_ALLOCATION : contributes
    SALES_ORDER_LINE ||--o{ BILLING_ALLOCATION : billed_by
    INVOICE_LINE ||--o{ BILLING_ALLOCATION : allocates
    INVOICE ||--|{ INVOICE_LINE : contains
    PARTY ||--o{ INVOICE : counterparty
    INVOICE ||--o{ PAYMENT_ALLOCATION : settled_by
    PAYMENT ||--o{ PAYMENT_ALLOCATION : allocates
    INVOICE ||--o{ JOURNAL_ENTRY : posted_as
    JOURNAL_ENTRY ||--|{ JOURNAL_LINE : contains
    PURCHASE_ORDER ||--|{ PURCHASE_ORDER_LINE : contains
    PURCHASE_ORDER_LINE ||--o{ RECEIPT_ALLOCATION : received_by
    STOCK_MOVE ||--o{ RECEIPT_ALLOCATION : contributes
    STOCK_MOVE ||--o{ VALUATION_LAYER : valued_by
    ITEM ||--o{ STOCK_MOVE : moved
    PROJECT ||--o{ TIME_ENTRY : consumes
    EMPLOYEE ||--o{ TIME_ENTRY : records
    EQUIPMENT ||--o{ WORK_ORDER : serviced_by
    PROJECT ||--o{ WORK_ORDER : charged_to
```

## Referential rules

- Validate legal company and tenant scope for every link.
- All parent-to-child document line relations should be indexed for drill-down and reconciliation.
- Prevent deletion of posted history and disallow orphaned allocations.
- Do not assume a document number is unique across entities, companies or instances.
- Use independent document status and fulfillment/billing status; don't collapse them into one boolean.
- Reconcile quantities, amounts, taxes, currencies and sign conventions at integration boundaries.
