-- =====================================================================
--  Module catalogue seed — the dynamic product/pricing source of truth.
--  Edit prices/rows here OR via the control panel; app code never hardcodes them.
--  ON CONFLICT keeps existing edits (idempotent, non-destructive).
-- =====================================================================
INSERT INTO module_catalogue (key, name, description, icon, category, price_usd, price_aed, is_free, is_core, odoo_module, sort_order) VALUES
('einvoicing',  'E-Invoicing & VAT',     'UAE VAT QR, ZATCA Phase 2, FBR. Auto-submits on every invoice.',          '🧾','compliance',  0,   0,   TRUE,  TRUE,  'mumtaz_einvoicing',          1),
('crm',         'CRM & Sales Pipeline',  '7-stage pipeline for GCC and Pakistan. Leads, quotations, customers.',     '📊','sales',       0,   0,   TRUE,  TRUE,  'mumtaz_crm_starter',         2),
('accounting',  'Accounting & Finance',  'Double-entry books, P&L, balance sheet, bank reconciliation.',             '📚','finance',     20,  75,  FALSE, FALSE, 'account,account_accountant', 3),
('inventory',   'Inventory & Purchasing','Stock management, purchase orders, reorder rules, valuation.',              '📦','operations',  20,  75,  FALSE, FALSE, 'stock,purchase',             4),
('hr_payroll',  'HR & Payroll',          'Employee records, payslips, WPS, Pakistan payroll, leave.',                '👥','hr',          25,  95,  FALSE, FALSE, 'hr,hr_payroll',              5),
('projects',    'Projects & Timesheets', 'Task management, milestones, timesheets, Gantt charts.',                   '📋','productivity',12,  45,  FALSE, FALSE, 'project',                    6),
('manufacturing','Manufacturing (MRP)',  'Bill of materials, production orders, work centres, quality.',             '🏭','operations',  30,  110, FALSE, FALSE, 'mrp',                        7),
('marketplace', 'B2B Marketplace',       'Buy/sell inside the Mumtaz network. OWL PO widget. 1.5% fee.',             '⟁','network',     15,  55,  FALSE, FALSE, 'mumtaz_marketplace',         8),
('zaki',        'Zaki AI CFO',           'Voice AI CFO. Morning briefings, health scores, board packs.',            'ذ','ai',          35,  130, FALSE, FALSE, 'mumtaz_zaki',                9),
('vendor_portal','Vendor Portal',        'Self-service portal for suppliers: POs, RFQs, receipts, payments.',        '🏪','operations',  10,  38,  FALSE, FALSE, 'mumtaz_vendor_portal',      10),
('finance_sdk', 'Embedded Finance SDK',  'Embedded ledger, wallet, business accounts, cards.',                       '💳','finance',     50,  185, FALSE, FALSE, 'mumtaz_finance',            11)
ON CONFLICT (key) DO NOTHING;
