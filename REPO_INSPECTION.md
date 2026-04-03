# Repository Inspection Report

- Date: 2026-04-02
- Method: static inspection of tracked repository files and addon manifests (`git ls-files`).

## Executive Summary
- Repository currently contains **239 tracked files**.
- Primary stack is an **Odoo addon monorepo** with **16 installable addons** under `addons/`, plus deployment configs, a static website, and scraper utilities.
- Inspection includes inventory + architecture surface + quick static risk indicators.

## Repository Composition
- Python: **133**
- XML: **63**
- CSV: **14**
- HTML: **11**
- JavaScript: **2**
- CSS: **1**

## Addon Matrix
| Addon | Version | Depends | Models | Services | Controllers | Wizards | Purpose |
|---|---|---|---:|---:|---:|---:|---|
| `mumtaz_ai` | 19.0.1.2.0 | `base, mail, account, mumtaz_core` | 2 | 1 | 0 | 0 | Pluggable AI interaction layer for Odoo Community |
| `mumtaz_base` | 19.0.1.2.0 | `base, contacts` | 1 | 0 | 0 | 0 | Base customizations for Mumtaz in Odoo Community |
| `mumtaz_branding` | 19.0.1.0.0 | `mumtaz_core` | 1 | 0 | 0 | 0 | White-label brand configuration engine for Mumtaz platform partners |
| `mumtaz_cfo_base` | 19.0.1.0.0 | `base, mail` | 2 | 0 | 0 | 0 | Workspace and category foundation for Mumtaz v1 CFO toolkit |
| `mumtaz_cfo_ingestion` | 19.0.1.0.0 | `mumtaz_cfo_base` | 3 | 0 | 0 | 0 | Upload and mapping foundation for Mumtaz CFO transaction ingestion |
| `mumtaz_cfo_toolkit` | 19.0.1.0.0 | `mumtaz_cfo_base, mumtaz_cfo_ingestion, mumtaz_cfo_transactions` | 0 | 0 | 0 | 0 | Compact installer module for CFO base, ingestion, and transactions |
| `mumtaz_cfo_transactions` | 19.0.1.0.0 | `mumtaz_cfo_ingestion` | 3 | 1 | 0 | 0 | Normalized transaction engine and review workflow for Mumtaz CFO |
| `mumtaz_core` | 19.0.1.2.0 | `base, mail, base_setup` | 3 | 0 | 0 | 0 | Core configuration and logging for Mumtaz AI Agent |
| `mumtaz_lead_nurture` | 19.0.1.0.0 | `crm, mail, mumtaz_lead_scraper` | 8 | 5 | 0 | 2 | Lead nurturing, qualification, and auto-conversion engine for Odoo ERP sales |
| `mumtaz_lead_scraper` | 19.0.1.0.0 | `base, mail, crm` | 3 | 8 | 0 | 1 | Configurable lead scraping engine with CRM integration |
| `mumtaz_marketplace` | 19.0.1.0.0 | `mumtaz_sme_profile, mail` | 3 | 0 | 0 | 0 | B2B marketplace for SMEs to list and discover products and services |
| `mumtaz_onboarding` | 19.0.1.0.0 | `mumtaz_sme_profile` | 1 | 0 | 0 | 0 | Guided SME onboarding checklists and progress tracking |
| `mumtaz_sme_profile` | 19.0.1.0.0 | `mumtaz_branding` | 1 | 0 | 0 | 0 | SME company profile, classification, and lifecycle management |
| `mumtaz_super_toolkit` | 19.0.1.0.0 | `mumtaz_base, mumtaz_cfo_toolkit` | 0 | 0 | 0 | 0 | Single-click installer for Mumtaz base + CFO toolkit |
| `mumtaz_tenant_manager` | 19.0.1.0.0 | `base, mail, mumtaz_branding` | 2 | 1 | 0 | 1 | Central control plane for managing isolated Odoo tenants in the Mumtaz SaaS platform |
| `mumtaz_voice` | 19.0.1.0.0 | `mumtaz_ai, mumtaz_core, account` | 2 | 2 | 1 | 0 | AI-powered CFO Voice Assistant - query your Odoo financials by voice or text |

## Quick Static Risk Indicators (heuristic)
- These are **signals**, not confirmed defects.
- Broad `except Exception` occurrences: **35**
- `.sudo(...)` occurrences (Python/XML): **7**
- `requests.` call references (Python): **26**
- `TODO/FIXME/HACK/XXX` marker occurrences: **4**

## Top-Level Areas (tracked file count)
- `(root)/`: 3
- `addons/`: 197
- `apps/`: 15
- `ops/`: 7
- `tools/`: 17

## Complete File Inventory (tracked files)
- `.gitignore`
- `.mcp.json`
- `REPO_INSPECTION.md`
- `addons/mumtaz_ai/__init__.py`
- `addons/mumtaz_ai/__manifest__.py`
- `addons/mumtaz_ai/models/__init__.py`
- `addons/mumtaz_ai/models/mumtaz_ai_message.py`
- `addons/mumtaz_ai/models/mumtaz_ai_session.py`
- `addons/mumtaz_ai/providers/__init__.py`
- `addons/mumtaz_ai/providers/anthropic_provider.py`
- `addons/mumtaz_ai/providers/base_provider.py`
- `addons/mumtaz_ai/providers/openai_provider.py`
- `addons/mumtaz_ai/security/ir.model.access.csv`
- `addons/mumtaz_ai/security/mumtaz_ai_security.xml`
- `addons/mumtaz_ai/services/__init__.py`
- `addons/mumtaz_ai/services/ai_service.py`
- `addons/mumtaz_ai/views/mumtaz_ai_session_views.xml`
- `addons/mumtaz_base/__init__.py`
- `addons/mumtaz_base/__manifest__.py`
- `addons/mumtaz_base/models/__init__.py`
- `addons/mumtaz_base/models/res_partner.py`
- `addons/mumtaz_base/security/ir.model.access.csv`
- `addons/mumtaz_base/views/res_partner_views.xml`
- `addons/mumtaz_branding/__init__.py`
- `addons/mumtaz_branding/__manifest__.py`
- `addons/mumtaz_branding/models/__init__.py`
- `addons/mumtaz_branding/models/mumtaz_brand.py`
- `addons/mumtaz_branding/security/ir.model.access.csv`
- `addons/mumtaz_branding/views/mumtaz_brand_views.xml`
- `addons/mumtaz_cfo_base/__init__.py`
- `addons/mumtaz_cfo_base/__manifest__.py`
- `addons/mumtaz_cfo_base/data/cfo_category_data.xml`
- `addons/mumtaz_cfo_base/models/__init__.py`
- `addons/mumtaz_cfo_base/models/cfo_category.py`
- `addons/mumtaz_cfo_base/models/cfo_workspace.py`
- `addons/mumtaz_cfo_base/security/cfo_base_rules.xml`
- `addons/mumtaz_cfo_base/security/cfo_base_security.xml`
- `addons/mumtaz_cfo_base/security/ir.model.access.csv`
- `addons/mumtaz_cfo_base/views/cfo_category_views.xml`
- `addons/mumtaz_cfo_base/views/cfo_menus.xml`
- `addons/mumtaz_cfo_base/views/cfo_workspace_views.xml`
- `addons/mumtaz_cfo_ingestion/__init__.py`
- `addons/mumtaz_cfo_ingestion/__manifest__.py`
- `addons/mumtaz_cfo_ingestion/models/__init__.py`
- `addons/mumtaz_cfo_ingestion/models/cfo_data_source.py`
- `addons/mumtaz_cfo_ingestion/models/cfo_mapping_profile.py`
- `addons/mumtaz_cfo_ingestion/models/cfo_upload_batch.py`
- `addons/mumtaz_cfo_ingestion/security/cfo_ingestion_rules.xml`
- `addons/mumtaz_cfo_ingestion/security/ir.model.access.csv`
- `addons/mumtaz_cfo_ingestion/views/cfo_data_source_views.xml`
- `addons/mumtaz_cfo_ingestion/views/cfo_ingestion_menus.xml`
- `addons/mumtaz_cfo_ingestion/views/cfo_mapping_profile_views.xml`
- `addons/mumtaz_cfo_ingestion/views/cfo_upload_batch_views.xml`
- `addons/mumtaz_cfo_toolkit/__init__.py`
- `addons/mumtaz_cfo_toolkit/__manifest__.py`
- `addons/mumtaz_cfo_transactions/__init__.py`
- `addons/mumtaz_cfo_transactions/__manifest__.py`
- `addons/mumtaz_cfo_transactions/models/__init__.py`
- `addons/mumtaz_cfo_transactions/models/cfo_review_item.py`
- `addons/mumtaz_cfo_transactions/models/cfo_transaction.py`
- `addons/mumtaz_cfo_transactions/models/cfo_upload_batch.py`
- `addons/mumtaz_cfo_transactions/security/cfo_transactions_rules.xml`
- `addons/mumtaz_cfo_transactions/security/ir.model.access.csv`
- `addons/mumtaz_cfo_transactions/services/__init__.py`
- `addons/mumtaz_cfo_transactions/services/ingestion_service.py`
- `addons/mumtaz_cfo_transactions/views/cfo_review_item_views.xml`
- `addons/mumtaz_cfo_transactions/views/cfo_transaction_views.xml`
- `addons/mumtaz_cfo_transactions/views/cfo_transactions_menus.xml`
- `addons/mumtaz_cfo_transactions/views/cfo_upload_batch_views.xml`
- `addons/mumtaz_core/__init__.py`
- `addons/mumtaz_core/__manifest__.py`
- `addons/mumtaz_core/data/mumtaz_core_data.xml`
- `addons/mumtaz_core/models/__init__.py`
- `addons/mumtaz_core/models/mumtaz_config_settings.py`
- `addons/mumtaz_core/models/mumtaz_core_log.py`
- `addons/mumtaz_core/models/mumtaz_core_settings.py`
- `addons/mumtaz_core/security/ir.model.access.csv`
- `addons/mumtaz_core/security/mumtaz_core_rules.xml`
- `addons/mumtaz_core/security/mumtaz_core_security.xml`
- `addons/mumtaz_core/views/mumtaz_core_settings_views.xml`
- `addons/mumtaz_core/views/mumtaz_log_views.xml`
- `addons/mumtaz_core/views/mumtaz_res_config_settings_views.xml`
- `addons/mumtaz_lead_nurture/__init__.py`
- `addons/mumtaz_lead_nurture/__manifest__.py`
- `addons/mumtaz_lead_nurture/data/lead_nurture_cron.xml`
- `addons/mumtaz_lead_nurture/data/lead_nurture_data.xml`
- `addons/mumtaz_lead_nurture/models/__init__.py`
- `addons/mumtaz_lead_nurture/models/crm_lead_ext.py`
- `addons/mumtaz_lead_nurture/models/lead_nurture_campaign.py`
- `addons/mumtaz_lead_nurture/models/lead_nurture_erp_need.py`
- `addons/mumtaz_lead_nurture/models/lead_nurture_log.py`
- `addons/mumtaz_lead_nurture/models/lead_nurture_rule.py`
- `addons/mumtaz_lead_nurture/models/lead_nurture_step.py`
- `addons/mumtaz_lead_nurture/models/whatsapp_provider.py`
- `addons/mumtaz_lead_nurture/models/whatsapp_template.py`
- `addons/mumtaz_lead_nurture/security/ir.model.access.csv`
- `addons/mumtaz_lead_nurture/security/lead_nurture_security.xml`
- `addons/mumtaz_lead_nurture/services/__init__.py`
- `addons/mumtaz_lead_nurture/services/conversion_engine.py`
- `addons/mumtaz_lead_nurture/services/email_service.py`
- `addons/mumtaz_lead_nurture/services/scoring_engine.py`
- `addons/mumtaz_lead_nurture/services/sequence_runner.py`
- `addons/mumtaz_lead_nurture/services/whatsapp_service.py`
- `addons/mumtaz_lead_nurture/views/crm_lead_ext_views.xml`
- `addons/mumtaz_lead_nurture/views/lead_nurture_campaign_views.xml`
- `addons/mumtaz_lead_nurture/views/lead_nurture_log_views.xml`
- `addons/mumtaz_lead_nurture/views/lead_nurture_menus.xml`
- `addons/mumtaz_lead_nurture/views/lead_nurture_rule_views.xml`
- `addons/mumtaz_lead_nurture/views/lead_nurture_wizard_views.xml`
- `addons/mumtaz_lead_nurture/views/whatsapp_views.xml`
- `addons/mumtaz_lead_nurture/wizards/__init__.py`
- `addons/mumtaz_lead_nurture/wizards/enroll_wizard.py`
- `addons/mumtaz_lead_nurture/wizards/qualify_wizard.py`
- `addons/mumtaz_lead_scraper/__init__.py`
- `addons/mumtaz_lead_scraper/__manifest__.py`
- `addons/mumtaz_lead_scraper/data/lead_scraper_cron.xml`
- `addons/mumtaz_lead_scraper/models/__init__.py`
- `addons/mumtaz_lead_scraper/models/lead_scraper_job.py`
- `addons/mumtaz_lead_scraper/models/lead_scraper_record.py`
- `addons/mumtaz_lead_scraper/models/lead_scraper_source.py`
- `addons/mumtaz_lead_scraper/security/ir.model.access.csv`
- `addons/mumtaz_lead_scraper/security/lead_scraper_security.xml`
- `addons/mumtaz_lead_scraper/services/__init__.py`
- `addons/mumtaz_lead_scraper/services/crm_mapper.py`
- `addons/mumtaz_lead_scraper/services/deduplicator.py`
- `addons/mumtaz_lead_scraper/services/difc_parser.py`
- `addons/mumtaz_lead_scraper/services/engine.py`
- `addons/mumtaz_lead_scraper/services/fetcher.py`
- `addons/mumtaz_lead_scraper/services/normalizer.py`
- `addons/mumtaz_lead_scraper/services/parser.py`
- `addons/mumtaz_lead_scraper/services/ptp_parser.py`
- `addons/mumtaz_lead_scraper/static/description/icon.png`
- `addons/mumtaz_lead_scraper/views/lead_scraper_job_views.xml`
- `addons/mumtaz_lead_scraper/views/lead_scraper_menus.xml`
- `addons/mumtaz_lead_scraper/views/lead_scraper_record_views.xml`
- `addons/mumtaz_lead_scraper/views/lead_scraper_source_views.xml`
- `addons/mumtaz_lead_scraper/views/lead_scraper_wizard_views.xml`
- `addons/mumtaz_lead_scraper/wizards/__init__.py`
- `addons/mumtaz_lead_scraper/wizards/lead_scraper_run_wizard.py`
- `addons/mumtaz_marketplace/__init__.py`
- `addons/mumtaz_marketplace/__manifest__.py`
- `addons/mumtaz_marketplace/data/mumtaz_marketplace_data.xml`
- `addons/mumtaz_marketplace/models/__init__.py`
- `addons/mumtaz_marketplace/models/marketplace_category.py`
- `addons/mumtaz_marketplace/models/marketplace_inquiry.py`
- `addons/mumtaz_marketplace/models/marketplace_listing.py`
- `addons/mumtaz_marketplace/security/ir.model.access.csv`
- `addons/mumtaz_marketplace/security/mumtaz_marketplace_rules.xml`
- `addons/mumtaz_marketplace/security/mumtaz_marketplace_security.xml`
- `addons/mumtaz_marketplace/views/mumtaz_marketplace_category_views.xml`
- `addons/mumtaz_marketplace/views/mumtaz_marketplace_inquiry_views.xml`
- `addons/mumtaz_marketplace/views/mumtaz_marketplace_listing_views.xml`
- `addons/mumtaz_marketplace/views/mumtaz_menus.xml`
- `addons/mumtaz_onboarding/__init__.py`
- `addons/mumtaz_onboarding/__manifest__.py`
- `addons/mumtaz_onboarding/models/__init__.py`
- `addons/mumtaz_onboarding/models/mumtaz_onboarding.py`
- `addons/mumtaz_onboarding/security/ir.model.access.csv`
- `addons/mumtaz_onboarding/security/mumtaz_onboarding_rules.xml`
- `addons/mumtaz_onboarding/views/mumtaz_onboarding_views.xml`
- `addons/mumtaz_sme_profile/__init__.py`
- `addons/mumtaz_sme_profile/__manifest__.py`
- `addons/mumtaz_sme_profile/models/__init__.py`
- `addons/mumtaz_sme_profile/models/mumtaz_sme_profile.py`
- `addons/mumtaz_sme_profile/security/ir.model.access.csv`
- `addons/mumtaz_sme_profile/security/mumtaz_sme_profile_rules.xml`
- `addons/mumtaz_sme_profile/views/mumtaz_sme_profile_views.xml`
- `addons/mumtaz_super_toolkit/__init__.py`
- `addons/mumtaz_super_toolkit/__manifest__.py`
- `addons/mumtaz_tenant_manager/__init__.py`
- `addons/mumtaz_tenant_manager/__manifest__.py`
- `addons/mumtaz_tenant_manager/data/mumtaz_bundle_data.xml`
- `addons/mumtaz_tenant_manager/models/__init__.py`
- `addons/mumtaz_tenant_manager/models/mumtaz_module_bundle.py`
- `addons/mumtaz_tenant_manager/models/mumtaz_tenant.py`
- `addons/mumtaz_tenant_manager/security/ir.model.access.csv`
- `addons/mumtaz_tenant_manager/security/mumtaz_tenant_security.xml`
- `addons/mumtaz_tenant_manager/services/__init__.py`
- `addons/mumtaz_tenant_manager/services/provisioning.py`
- `addons/mumtaz_tenant_manager/views/mumtaz_menus.xml`
- `addons/mumtaz_tenant_manager/views/mumtaz_module_bundle_views.xml`
- `addons/mumtaz_tenant_manager/views/mumtaz_tenant_views.xml`
- `addons/mumtaz_tenant_manager/views/provision_wizard_views.xml`
- `addons/mumtaz_tenant_manager/wizards/__init__.py`
- `addons/mumtaz_tenant_manager/wizards/provision_wizard.py`
- `addons/mumtaz_voice/__init__.py`
- `addons/mumtaz_voice/__manifest__.py`
- `addons/mumtaz_voice/controllers/__init__.py`
- `addons/mumtaz_voice/controllers/voice_controller.py`
- `addons/mumtaz_voice/models/__init__.py`
- `addons/mumtaz_voice/models/mumtaz_voice_message.py`
- `addons/mumtaz_voice/models/mumtaz_voice_session.py`
- `addons/mumtaz_voice/security/ir.model.access.csv`
- `addons/mumtaz_voice/security/mumtaz_voice_security.xml`
- `addons/mumtaz_voice/services/__init__.py`
- `addons/mumtaz_voice/services/cfo_service.py`
- `addons/mumtaz_voice/services/voice_service.py`
- `addons/mumtaz_voice/static/src/js/voice_assistant.js`
- `addons/mumtaz_voice/static/src/xml/voice_assistant.xml`
- `addons/mumtaz_voice/views/mumtaz_voice_views.xml`
- `apps/website/README.md`
- `apps/website/about.html`
- `apps/website/ai.html`
- `apps/website/assets/css/style.css`
- `apps/website/assets/images/favicon.svg`
- `apps/website/assets/js/main.js`
- `apps/website/banks.html`
- `apps/website/contact.html`
- `apps/website/demo.html`
- `apps/website/erp.html`
- `apps/website/finance.html`
- `apps/website/index.html`
- `apps/website/platform.html`
- `apps/website/pricing.html`
- `apps/website/smes.html`
- `ops/deployment/ODOO19_APP_DETECTION.md`
- `ops/deployment/check_mumtaz_modules.py`
- `ops/deployment/make_odoo_detect_mumtaz.sh`
- `ops/deployment/nginx-mumtaz-digital.conf`
- `ops/deployment/nginx_tenant_routing.conf`
- `ops/deployment/odoo_master.conf`
- `ops/deployment/odoo_tenant_worker.conf`
- `tools/scrapers/pakistan_trade_portal/INSPECTION.md`
- `tools/scrapers/pakistan_trade_portal/README.md`
- `tools/scrapers/pakistan_trade_portal/company_enrichment.py`
- `tools/scrapers/pakistan_trade_portal/company_extraction.py`
- `tools/scrapers/pakistan_trade_portal/config.py`
- `tools/scrapers/pakistan_trade_portal/contact_detection.py`
- `tools/scrapers/pakistan_trade_portal/enterprise_scraper_v2.py`
- `tools/scrapers/pakistan_trade_portal/models.py`
- `tools/scrapers/pakistan_trade_portal/normalize.py`
- `tools/scrapers/pakistan_trade_portal/odoo_push.py`
- `tools/scrapers/pakistan_trade_portal/portal_selectors.py`
- `tools/scrapers/pakistan_trade_portal/requirements.txt`
- `tools/scrapers/pakistan_trade_portal/run_company_extraction.py`
- `tools/scrapers/pakistan_trade_portal/run_enriched_companies.py`
- `tools/scrapers/pakistan_trade_portal/scoring.py`
- `tools/scrapers/pakistan_trade_portal/scrape.py`
- `tools/scrapers/pakistan_trade_portal/selectors.py`
