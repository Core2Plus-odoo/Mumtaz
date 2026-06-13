-- =====================================================================
--  Core ERP module catalogue corrections (idempotent).
--  - Map modules to Odoo COMMUNITY apps (account_accountant / hr_payroll
--    are Enterprise-only and fail to install on Community).
--  - Add the Sales app (sale_management) that was missing.
--  Safe to run repeatedly. Apply to the mumtaz_platform control-plane DB.
-- =====================================================================

-- Accounting: Community ships invoicing+accounting in `account`.
UPDATE module_catalogue
   SET odoo_module = 'account',
       description = 'Invoicing, double-entry books, P&L, balance sheet, bank reconciliation.'
 WHERE key = 'accounting';

-- HR: drop the Enterprise `hr_payroll`; use Community HR + Time Off.
UPDATE module_catalogue
   SET odoo_module = 'hr,hr_holidays',
       name        = 'HR & Employees',
       description = 'Employee records, departments, time off, attendance, expenses.'
 WHERE key = 'hr_payroll';

-- Sales: quotations / sales orders (was missing — crm maps to our starter).
INSERT INTO module_catalogue
    (key, name, description, icon, category, price_usd, price_aed, is_free, is_core, odoo_module, sort_order)
VALUES
    ('sales', 'Sales & Quotations',
     'Quotations, sales orders, customer invoicing, pricelists, deliveries.',
     '🛒', 'sales', 15, 55, FALSE, FALSE, 'sale_management', 3)
ON CONFLICT (key) DO UPDATE
    SET odoo_module = EXCLUDED.odoo_module,
        name        = EXCLUDED.name,
        description = EXCLUDED.description;

-- Keep the rest sequential after the inserted Sales row.
UPDATE module_catalogue SET sort_order = 4  WHERE key = 'accounting';
UPDATE module_catalogue SET sort_order = 5  WHERE key = 'inventory';
UPDATE module_catalogue SET sort_order = 6  WHERE key = 'hr_payroll';
UPDATE module_catalogue SET sort_order = 7  WHERE key = 'projects';
UPDATE module_catalogue SET sort_order = 8  WHERE key = 'manufacturing';
UPDATE module_catalogue SET sort_order = 9  WHERE key = 'marketplace';
UPDATE module_catalogue SET sort_order = 10 WHERE key = 'zaki';
UPDATE module_catalogue SET sort_order = 11 WHERE key = 'vendor_portal';
UPDATE module_catalogue SET sort_order = 12 WHERE key = 'finance_sdk';
