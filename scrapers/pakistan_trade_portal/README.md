# Pakistan Trade Portal Scraper

This module provides a business-development oriented scraper scaffold for the Pakistan Trade Portal.

## Objective

Capture publicly visible exporter and product listing data, score prospects for ERP/business consulting relevance, and prepare structured output for import into Odoo CRM or a custom lead model.

## Scope

- Sector/category crawling
- Product/company listing extraction
- Lead scoring for business development
- CSV export for review
- Optional Odoo XML-RPC push

## Recommended workflow

1. Run the scraper in dry mode to collect raw records.
2. Review the CSV output and scoring.
3. Push qualified records into Odoo CRM.
4. Later, convert the workflow into a native Odoo module/cron if needed.

## Files

- `config.py` - configuration values
- `models.py` - dataclasses for raw and scored leads
- `scoring.py` - business-development scoring rules
- `scrape.py` - lightweight homepage scraper
- `run_enriched_companies.py` - enriched company discovery + scoring pipeline
- `portal_selectors.py` - CSS selector bank for resilient extraction
- `requirements.txt` - Python dependencies

## Run

```bash
cd scrapers/pakistan_trade_portal
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_enriched_companies.py
```

## Important note

Use only on publicly accessible pages, respect the portal's published terms, and keep request pacing conservative.
