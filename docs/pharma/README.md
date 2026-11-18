# Pharma ERP: core logic and DEMO (v0.1, all data fictional)

- pharma_core/tax_engine.py     effective-dated, approved-only tax rules; unresolved treatment blocks posting
- pharma_core/reconciliation.py exact-ref precedence, one-to-many, no amount-only ambiguous match, COD variance
- pharma_core/partner.py            Distribution Partner stock roll-forward; scenario gate (A/B/C not finalized; custody != sale)
- pharma_core/staging.py        immutable raw archive, idempotent posting, conflict queue
- tests/test_core.py            31 tests mapped to Blueprint s.23 UAT cases  (python3 -m pytest -q)
- build_demo.py + demo_template.html -> demo/index.html (drillable SAP-style list reports)
- templates/SKU_Tax_Classification_Template.csv  blank, PENDING_EVIDENCE

NOT verified: nothing here has been installed into Odoo. These are framework-independent reference
implementations whose rules will be ported into Odoo 19 Community addons (Phase 2+).
No production system was touched.
