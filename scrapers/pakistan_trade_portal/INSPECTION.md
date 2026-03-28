# Pakistan Trade Portal Scraper Inspection

Date: 2026-03-28  
Scope: `scrapers/pakistan_trade_portal`

## What this module currently does

- Collects public listing/company hints from the Pakistan Trade Portal.
- Normalizes candidate records into `RawTradeRecord`/`ScoredTradeLead` dataclasses.
- Applies heuristic scoring for lead qualification (`A/B/C`) and suggested offer.
- Exports enriched rows to CSV (`enriched_company_leads.csv`).

## Pipeline map

1. `run_enriched_companies.py` fetches `BASE_URL` and discovers candidate pages.
2. Selector-driven extraction (`portal_selectors.py`) collects company/city/sector.
3. Dedupe is applied by `(company_name, company_url)`.
4. `scoring.score_lead` assigns score + qualification.
5. CSV is written with all score/metadata fields.

## Inspection findings

### Strengths
- Dataclass-based schema is explicit and easy to map into CRM imports.
- Scoring logic is deterministic and easy to tune.
- Selector lists are centralized and resilient to modest DOM changes.

### Gaps / risks
- Scraping currently has no retry/backoff for transient network failures.
- `MAX_PAGES` in `config.py` is defined but not used by enrichment pipeline.
- No automated tests around extraction/scoring behavior.
- Heuristic `_is_company_like` may produce false positives on generic anchor text.

## Immediate recommendations

1. Add unit tests for:
   - `score_lead` qualification thresholds.
   - `_is_company_like` true/false examples.
   - `_extract_records_from_soup` using static HTML fixtures.
2. Wire `MAX_PAGES` into `_candidate_pages` limit to keep crawl budget configurable.
3. Add optional retry/backoff (e.g., exponential retry on 429/5xx).
4. Add `--output` and `--max-pages` CLI args for repeatable runs.

## Commands used for this inspection

```bash
python -m compileall scrapers/pakistan_trade_portal
python scrapers/pakistan_trade_portal/run_enriched_companies.py
```
