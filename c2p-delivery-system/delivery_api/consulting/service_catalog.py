"""Consulting OS Layer 1–3: roles × client types × service catalog.

The static mapping model the wizard and intelligence engine run on:
which roles exist, which client segments, which services each role delivers,
and which services to auto-suggest for a (role, client_type) pair.
"""
from __future__ import annotations

ROLES = {
    "odoo_partner": "Odoo ERP Partner / Consultant",
    "bookkeeper": "Bookkeeper",
    "chartered_accountant": "Chartered Accountant",
    "management_consultant": "Management Consultant",
}

CLIENT_TYPES = {
    "trading": "Trading & Distribution",
    "manufacturing": "Manufacturing",
    "ecommerce_retail": "E-commerce / Retail",
    "services": "Services / Consulting Firms",
    "finance": "Finance / Corporate ERP",
    "enterprise": "Government / Enterprise",
}

# role -> {service_key: label}
SERVICE_CATALOG = {
    "odoo_partner": {
        "erp_implementation": "ERP Implementation",
        "odoo_customization": "Customization & Studio",
        "odoo_integration": "Integration (APIs / connectors)",
        "odoo_training": "Training & Enablement",
        "odoo_support": "Support & Optimisation (existing Odoo)",
        "data_migration_service": "Data Migration",
        "odoo_health_check": "Health Check & Optimisation",
        "analytics_bi": "Analytics & BI Dashboards",
        "erp_rescue": "ERP Rescue",
        "hypercare_support": "Hypercare & AMC",
    },
    "bookkeeper": {
        "bookkeeping": "Monthly Bookkeeping",
        "vat_filing": "VAT Filing (FTA/ZATCA)",
        "financial_reporting": "Financial Reporting",
        "payroll_processing": "Payroll Processing (WPS)",
    },
    "chartered_accountant": {
        "compliance_advisory": "Tax & Compliance Advisory",
        "audit_preparation": "Audit Preparation",
        "financial_reporting": "Financial Reporting (IFRS)",
        "cfo_advisory": "Virtual CFO / Advisory",
        "budgeting": "Budgeting & Forecasting",
    },
    "management_consultant": {
        "sop_design": "SOP Design",
        "bpr": "Business Process Reengineering",
        "strategy_consulting": "Strategy Consulting",
        "kpi_design": "KPI & Performance Framework",
        "change_management_service": "Change Management",
    },
}

# (role, client_type) -> default service keys (subset of the role's catalog).
SUGGEST = {
    ("odoo_partner", "trading"): ["erp_implementation", "odoo_integration"],
    ("odoo_partner", "manufacturing"): ["erp_implementation", "odoo_customization"],
    ("odoo_partner", "ecommerce_retail"): ["erp_implementation", "odoo_integration"],
    ("odoo_partner", "services"): ["erp_implementation", "odoo_training"],
    ("odoo_partner", "finance"): ["erp_implementation", "odoo_support"],
    ("odoo_partner", "enterprise"): ["erp_implementation", "odoo_customization", "odoo_integration"],
    ("bookkeeper", "trading"): ["bookkeeping", "vat_filing"],
    ("bookkeeper", "ecommerce_retail"): ["bookkeeping", "vat_filing"],
    ("bookkeeper", "services"): ["bookkeeping", "financial_reporting"],
    ("bookkeeper", "finance"): ["financial_reporting", "vat_filing"],
    ("chartered_accountant", "finance"): ["compliance_advisory", "financial_reporting"],
    ("chartered_accountant", "trading"): ["compliance_advisory", "audit_preparation"],
    ("chartered_accountant", "enterprise"): ["audit_preparation", "cfo_advisory"],
    ("management_consultant", "services"): ["sop_design", "bpr"],
    ("management_consultant", "manufacturing"): ["bpr", "kpi_design"],
    ("management_consultant", "enterprise"): ["strategy_consulting", "sop_design"],
}


def catalog() -> dict:
    """Everything the wizard needs in one payload."""
    return {"roles": ROLES, "client_types": CLIENT_TYPES,
            "services": SERVICE_CATALOG}


def suggest_services(roles: list, client_types: list) -> list:
    """Auto-suggested services for the selected roles × client types (union,
    role-catalog order, falling back to each role's first two services)."""
    out: list[str] = []
    for r in roles or []:
        hit = False
        for c in client_types or []:
            for s in SUGGEST.get((r, c), []):
                hit = True
                if s not in out:
                    out.append(s)
        if not hit:                                # no pair mapping → role defaults
            for s in list(SERVICE_CATALOG.get(r, {}))[:2]:
                if s not in out:
                    out.append(s)
    return out


def validate(roles: list, client_types: list, services: list) -> list:
    """Return human-readable problems (empty = valid)."""
    errs = []
    bad = [r for r in roles or [] if r not in ROLES]
    if bad:
        errs.append(f"Unknown role(s): {', '.join(bad)}")
    bad = [c for c in client_types or [] if c not in CLIENT_TYPES]
    if bad:
        errs.append(f"Unknown client type(s): {', '.join(bad)}")
    all_services = {s for cat in SERVICE_CATALOG.values() for s in cat}
    bad = [s for s in services or [] if s not in all_services]
    if bad:
        errs.append(f"Unknown service(s): {', '.join(bad)}")
    if not roles:
        errs.append("Select at least one role")
    return errs
