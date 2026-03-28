# Repository Inspection Report

- Date: 2026-03-28
- Scope: Full static inspection of repository files and addon structure.

## Snapshot
- Total tracked files (excluding `.git` internals): **156**
- Total Odoo addons (directories with `__manifest__.py`): **13**
- Python files: **82**, XML files: **39**, HTML files: **10**

## Odoo Addons and Dependencies
| Addon path | Name | Version | Depends | Summary |
|---|---|---|---|---|
| `mumtaz_ai` | Mumtaz AI | 19.0.1.2.0 | `base, mail, account, mumtaz_core` | Pluggable AI interaction layer for Odoo Community |
| `mumtaz_base` | Mumtaz Base | 19.0.1.2.0 | `base, contacts` | Base customizations for Mumtaz in Odoo Community |
| `mumtaz_branding` | Mumtaz Branding | 19.0.1.0.0 | `mumtaz_core` | White-label brand configuration engine for Mumtaz platform partners |
| `mumtaz_cfo_base` | Mumtaz CFO Base | 19.0.1.0.0 | `base, mail` | Workspace and category foundation for Mumtaz v1 CFO toolkit |
| `mumtaz_cfo_ingestion` | Mumtaz CFO Ingestion | 19.0.1.0.0 | `mumtaz_cfo_base` | Upload and mapping foundation for Mumtaz CFO transaction ingestion |
| `mumtaz_cfo_toolkit` | Mumtaz CFO Toolkit | 19.0.1.0.0 | `mumtaz_cfo_base, mumtaz_cfo_ingestion, mumtaz_cfo_transactions` | Compact installer module for CFO base, ingestion, and transactions |
| `mumtaz_cfo_transactions` | Mumtaz CFO Transactions | 19.0.1.0.0 | `mumtaz_cfo_ingestion` | Normalized transaction engine and review workflow for Mumtaz CFO |
| `mumtaz_core` | Mumtaz Core | 19.0.1.2.0 | `base, mail, base_setup` | Core configuration and logging for Mumtaz AI Agent |
| `mumtaz_onboarding` | Mumtaz Onboarding | 19.0.1.0.0 | `mumtaz_sme_profile` | Guided SME onboarding checklists and progress tracking |
| `mumtaz_sme_profile` | Mumtaz SME Profile | 19.0.1.0.0 | `mumtaz_branding` | SME company profile, classification, and lifecycle management |
| `mumtaz_super_toolkit` | Mumtaz Super Toolkit | 19.0.1.0.0 | `mumtaz_base, mumtaz_cfo_toolkit` | Single-click installer for Mumtaz base + CFO toolkit |
| `mumtaz_tenant_manager` | Mumtaz Tenant Manager | 19.0.1.0.0 | `base, mail, mumtaz_branding` | Central control plane for managing isolated Odoo tenants in the Mumtaz SaaS platform |
| `mumtaz_voice` | Mumtaz CFO Voice Assistant | 19.0.1.0.0 | `mumtaz_ai, mumtaz_core, account` | AI-powered CFO Voice Assistant - query your Odoo financials by voice or text |

## HTTP Controllers / Routes
- `mumtaz_voice/controllers/voice_controller.py`

## Top-level Areas
- `deployment/`: 6 files
- `mumtaz_ai/`: 14 files
- `mumtaz_base/`: 6 files
- `mumtaz_branding/`: 6 files
- `mumtaz_cfo_base/`: 12 files
- `mumtaz_cfo_ingestion/`: 12 files
- `mumtaz_cfo_toolkit/`: 2 files
- `mumtaz_cfo_transactions/`: 14 files
- `mumtaz_core/`: 13 files
- `mumtaz_onboarding/`: 7 files
- `mumtaz_sme_profile/`: 7 files
- `mumtaz_super_toolkit/`: 2 files
- `mumtaz_tenant_manager/`: 16 files
- `mumtaz_voice/`: 15 files
- `scrapers/`: 8 files
- `website/`: 14 files

## Complete File Inventory
- `.gitignore`
- `.mcp.json`
- `deployment/ODOO19_APP_DETECTION.md`
- `deployment/check_mumtaz_modules.py`
- `deployment/make_odoo_detect_mumtaz.sh`
- `deployment/nginx_tenant_routing.conf`
- `deployment/odoo_master.conf`
- `deployment/odoo_tenant_worker.conf`
- `mumtaz_ai/__init__.py`
- `mumtaz_ai/__manifest__.py`
- `mumtaz_ai/models/__init__.py`
- `mumtaz_ai/models/mumtaz_ai_message.py`
- `mumtaz_ai/models/mumtaz_ai_session.py`
- `mumtaz_ai/providers/__init__.py`
- `mumtaz_ai/providers/anthropic_provider.py`
- `mumtaz_ai/providers/base_provider.py`
- `mumtaz_ai/providers/openai_provider.py`
- `mumtaz_ai/security/ir.model.access.csv`
- `mumtaz_ai/security/mumtaz_ai_security.xml`
- `mumtaz_ai/services/__init__.py`
- `mumtaz_ai/services/ai_service.py`
- `mumtaz_ai/views/mumtaz_ai_session_views.xml`
- `mumtaz_base/__init__.py`
- `mumtaz_base/__manifest__.py`
- `mumtaz_base/models/__init__.py`
- `mumtaz_base/models/res_partner.py`
- `mumtaz_base/security/ir.model.access.csv`
- `mumtaz_base/views/res_partner_views.xml`
- `mumtaz_branding/__init__.py`
- `mumtaz_branding/__manifest__.py`
- `mumtaz_branding/models/__init__.py`
- `mumtaz_branding/models/mumtaz_brand.py`
- `mumtaz_branding/security/ir.model.access.csv`
- `mumtaz_branding/views/mumtaz_brand_views.xml`
- `mumtaz_cfo_base/__init__.py`
- `mumtaz_cfo_base/__manifest__.py`
- `mumtaz_cfo_base/data/cfo_category_data.xml`
- `mumtaz_cfo_base/models/__init__.py`
- `mumtaz_cfo_base/models/cfo_category.py`
- `mumtaz_cfo_base/models/cfo_workspace.py`
- `mumtaz_cfo_base/security/cfo_base_rules.xml`
- `mumtaz_cfo_base/security/cfo_base_security.xml`
- `mumtaz_cfo_base/security/ir.model.access.csv`
- `mumtaz_cfo_base/views/cfo_category_views.xml`
- `mumtaz_cfo_base/views/cfo_menus.xml`
- `mumtaz_cfo_base/views/cfo_workspace_views.xml`
- `mumtaz_cfo_ingestion/__init__.py`
- `mumtaz_cfo_ingestion/__manifest__.py`
- `mumtaz_cfo_ingestion/models/__init__.py`
- `mumtaz_cfo_ingestion/models/cfo_data_source.py`
- `mumtaz_cfo_ingestion/models/cfo_mapping_profile.py`
- `mumtaz_cfo_ingestion/models/cfo_upload_batch.py`
- `mumtaz_cfo_ingestion/security/cfo_ingestion_rules.xml`
- `mumtaz_cfo_ingestion/security/ir.model.access.csv`
- `mumtaz_cfo_ingestion/views/cfo_data_source_views.xml`
- `mumtaz_cfo_ingestion/views/cfo_ingestion_menus.xml`
- `mumtaz_cfo_ingestion/views/cfo_mapping_profile_views.xml`
- `mumtaz_cfo_ingestion/views/cfo_upload_batch_views.xml`
- `mumtaz_cfo_toolkit/__init__.py`
- `mumtaz_cfo_toolkit/__manifest__.py`
- `mumtaz_cfo_transactions/__init__.py`
- `mumtaz_cfo_transactions/__manifest__.py`
- `mumtaz_cfo_transactions/models/__init__.py`
- `mumtaz_cfo_transactions/models/cfo_review_item.py`
- `mumtaz_cfo_transactions/models/cfo_transaction.py`
- `mumtaz_cfo_transactions/models/cfo_upload_batch.py`
- `mumtaz_cfo_transactions/security/cfo_transactions_rules.xml`
- `mumtaz_cfo_transactions/security/ir.model.access.csv`
- `mumtaz_cfo_transactions/services/__init__.py`
- `mumtaz_cfo_transactions/services/ingestion_service.py`
- `mumtaz_cfo_transactions/views/cfo_review_item_views.xml`
- `mumtaz_cfo_transactions/views/cfo_transaction_views.xml`
- `mumtaz_cfo_transactions/views/cfo_transactions_menus.xml`
- `mumtaz_cfo_transactions/views/cfo_upload_batch_views.xml`
- `mumtaz_core/__init__.py`
- `mumtaz_core/__manifest__.py`
- `mumtaz_core/data/mumtaz_core_data.xml`
- `mumtaz_core/models/__init__.py`
- `mumtaz_core/models/mumtaz_config_settings.py`
- `mumtaz_core/models/mumtaz_core_log.py`
- `mumtaz_core/models/mumtaz_core_settings.py`
- `mumtaz_core/security/ir.model.access.csv`
- `mumtaz_core/security/mumtaz_core_rules.xml`
- `mumtaz_core/security/mumtaz_core_security.xml`
- `mumtaz_core/views/mumtaz_core_settings_views.xml`
- `mumtaz_core/views/mumtaz_log_views.xml`
- `mumtaz_core/views/mumtaz_res_config_settings_views.xml`
- `mumtaz_onboarding/__init__.py`
- `mumtaz_onboarding/__manifest__.py`
- `mumtaz_onboarding/models/__init__.py`
- `mumtaz_onboarding/models/mumtaz_onboarding.py`
- `mumtaz_onboarding/security/ir.model.access.csv`
- `mumtaz_onboarding/security/mumtaz_onboarding_rules.xml`
- `mumtaz_onboarding/views/mumtaz_onboarding_views.xml`
- `mumtaz_sme_profile/__init__.py`
- `mumtaz_sme_profile/__manifest__.py`
- `mumtaz_sme_profile/models/__init__.py`
- `mumtaz_sme_profile/models/mumtaz_sme_profile.py`
- `mumtaz_sme_profile/security/ir.model.access.csv`
- `mumtaz_sme_profile/security/mumtaz_sme_profile_rules.xml`
- `mumtaz_sme_profile/views/mumtaz_sme_profile_views.xml`
- `mumtaz_super_toolkit/__init__.py`
- `mumtaz_super_toolkit/__manifest__.py`
- `mumtaz_tenant_manager/__init__.py`
- `mumtaz_tenant_manager/__manifest__.py`
- `mumtaz_tenant_manager/data/mumtaz_bundle_data.xml`
- `mumtaz_tenant_manager/models/__init__.py`
- `mumtaz_tenant_manager/models/mumtaz_module_bundle.py`
- `mumtaz_tenant_manager/models/mumtaz_tenant.py`
- `mumtaz_tenant_manager/security/ir.model.access.csv`
- `mumtaz_tenant_manager/security/mumtaz_tenant_security.xml`
- `mumtaz_tenant_manager/services/__init__.py`
- `mumtaz_tenant_manager/services/provisioning.py`
- `mumtaz_tenant_manager/views/mumtaz_menus.xml`
- `mumtaz_tenant_manager/views/mumtaz_module_bundle_views.xml`
- `mumtaz_tenant_manager/views/mumtaz_tenant_views.xml`
- `mumtaz_tenant_manager/views/provision_wizard_views.xml`
- `mumtaz_tenant_manager/wizards/__init__.py`
- `mumtaz_tenant_manager/wizards/provision_wizard.py`
- `mumtaz_voice/__init__.py`
- `mumtaz_voice/__manifest__.py`
- `mumtaz_voice/controllers/__init__.py`
- `mumtaz_voice/controllers/voice_controller.py`
- `mumtaz_voice/models/__init__.py`
- `mumtaz_voice/models/mumtaz_voice_message.py`
- `mumtaz_voice/models/mumtaz_voice_session.py`
- `mumtaz_voice/security/ir.model.access.csv`
- `mumtaz_voice/security/mumtaz_voice_security.xml`
- `mumtaz_voice/services/__init__.py`
- `mumtaz_voice/services/cfo_service.py`
- `mumtaz_voice/services/voice_service.py`
- `mumtaz_voice/static/src/js/voice_assistant.js`
- `mumtaz_voice/static/src/xml/voice_assistant.xml`
- `mumtaz_voice/views/mumtaz_voice_views.xml`
- `scrapers/pakistan_trade_portal/README.md`
- `scrapers/pakistan_trade_portal/config.py`
- `scrapers/pakistan_trade_portal/models.py`
- `scrapers/pakistan_trade_portal/portal_selectors.py`
- `scrapers/pakistan_trade_portal/requirements.txt`
- `scrapers/pakistan_trade_portal/run_enriched_companies.py`
- `scrapers/pakistan_trade_portal/scoring.py`
- `scrapers/pakistan_trade_portal/scrape.py`
- `website/README.md`
- `website/about.html`
- `website/ai.html`
- `website/assets/css/style.css`
- `website/assets/images/favicon.svg`
- `website/assets/js/main.js`
- `website/banks.html`
- `website/contact.html`
- `website/demo.html`
- `website/erp.html`
- `website/finance.html`
- `website/index.html`
- `website/platform.html`
- `website/smes.html`
