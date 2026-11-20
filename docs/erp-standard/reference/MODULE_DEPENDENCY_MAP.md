# Suggested ERP Module Dependency Map

This diagram is a **conceptual domain dependency map**, not an auto-install list. Adjust after checking the target platform and client scope. Keep optional modules independently installable.

```mermaid
flowchart TD
    ORG[Organization, Legal Companies, Branches] --> IAM[Users, Roles, Approvals]
    ORG --> CFG[Currency, Tax, Fiscal Setup]
    ORG --> PARTY[Partners & Contacts]
    ORG --> ITEMS[Product / Service Master]
    IAM --> CRM[CRM]
    PARTY --> CRM
    PARTY --> SALES[Sales and Contracts]
    ITEMS --> SALES
    CRM --> SALES
    PARTY --> BUY[Procurement]
    ITEMS --> BUY
    ITEMS --> STOCK[Inventory & Valuation]
    BUY --> STOCK
    SALES --> STOCK
    CFG --> GL[General Ledger]
    STOCK --> GL
    SALES --> AR[Customer Invoices / AR]
    BUY --> AP[Vendor Bills / AP]
    AR --> GL
    AP --> GL
    PAY[Payments & Bank Reconciliation] --> GL
    AR --> PAY
    AP --> PAY
    SALES --> PROJECT[Projects / Service]
    PROJECT --> GL
    PROJECT --> STOCK
    HR[Employees / Time / Expense / Payroll] --> PROJECT
    HR --> GL
    STOCK --> MFG[Manufacturing / Quality]
    BUY --> MFG
    GL --> BI[Analytics / CFO / Group Command Centre]
    SALES --> BI
    STOCK --> BI
    PROJECT --> BI
    BI --> AI[Governed AI / Recommendation Layer]
    IAM --> AI
    INT[Integration / Events / Audit / Documents] -.cross-cutting.-> SALES
    INT -.cross-cutting.-> BUY
    INT -.cross-cutting.-> GL
```

## Implementation sequencing

- Foundation first: organization, identity, tax/currency, partners, items, audit, documents and integration contract design.
- Ensure a minimal GL/financial control layer exists before going live with invoice posting or stock valuation requiring accounting.
- Implement quote-to-cash and procure-to-pay as **vertical slices** with reconciled documents, not as a one-time big bang.
- Build industry modules after their operational and finance dependencies pass verification.
- Add BI and AI after data definitions, role boundaries and source-of-truth reports are proven.

## Dependency anti-patterns

- An optional AI module must not own or post the finance ledger.
- A warehouse UI must not manipulate receivable balances.
- Sales and procurement must share defined catalog/party modules instead of maintaining duplicate masters.
- Do not place two-way technical dependencies between modules; use a declared adapter/integration module and contract where necessary.
- Do not mix shared departmental allocation with legal intercompany bookkeeping.
