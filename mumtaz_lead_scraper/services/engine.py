"""
Scraper Engine
==============
Orchestrates the full pipeline:
  fetch → parse → normalize → deduplicate → create records → (optional) push to CRM
"""

import datetime
import logging

from .fetcher import PageFetcher
from .parser import get_parser
from .normalizer import Normalizer
from .deduplicator import Deduplicator
from .crm_mapper import CRMMapper

_logger = logging.getLogger(__name__)


class ScraperEngine:
    """Main orchestrator. Call run(source) to execute a full scraping job."""

    def __init__(self, env):
        self.env = env
        self.normalizer = Normalizer()
        self.deduplicator = Deduplicator(env)
        self.crm_mapper = CRMMapper(env)

    def run(self, source, auto_push_crm=False, triggered_by="manual"):
        """
        Execute a full scraping run for the given source record.
        Returns the created lead.scraper.job record.
        """
        job = self.env["lead.scraper.job"].create(
            {
                "source_id": source.id,
                "start_time": datetime.datetime.utcnow(),
                "status": "running",
                "triggered_by": triggered_by,
            }
        )

        job.append_log(f"Job started — source: {source.name}")
        job.append_log(f"URL: {source.url}")
        job.append_log(f"Mode: {source.parsing_mode} | Type: {source.source_type}")

        try:
            self._execute(job, source, auto_push_crm)
        except Exception as exc:
            _logger.exception("Engine error for source %s", source.name)
            job.write(
                {
                    "end_time": datetime.datetime.utcnow(),
                    "status": "failed",
                    "error_message": str(exc),
                }
            )
            job.append_log(f"FATAL ERROR: {exc}")

        # Update source last run timestamp
        source.write({"last_run_date": datetime.datetime.utcnow()})
        return job

    def _execute(self, job, source, auto_push_crm):
        # Dispatch to dedicated PTP engine if source type is ptp
        if source.source_type == "ptp":
            all_leads = self._execute_ptp(job, source)
        else:
            all_leads = self._execute_generic(job, source)
        self._save_leads(job, source, all_leads, auto_push_crm)

    def _execute_ptp(self, job, source):
        """Two-level scrape: collection page(s) → company detail pages."""
        from .ptp_parser import PTPListingParser, PTPDetailParser

        fetcher = PageFetcher(delay=source.request_delay or 2.0)
        listing_parser = PTPListingParser()
        detail_parser = PTPDetailParser()
        max_pages = source.max_pages or 20

        # --- Phase 1: collect all company URLs ---
        collection_queue = [source.url]
        collection_visited = set()
        company_urls = []
        collection_pages = 0

        while collection_queue and collection_pages < max_pages:
            col_url = collection_queue.pop(0)
            if col_url in collection_visited:
                continue
            collection_visited.add(col_url)

            if source.respect_robots and not fetcher.is_allowed_by_robots(col_url):
                job.append_log(f"Skipped (robots.txt): {col_url}")
                continue

            job.append_log(f"Fetching collection page: {col_url}")
            result = fetcher.fetch(col_url)
            if not result.success:
                job.append_log(f"Collection fetch failed [{result.status_code}]: {result.error}")
                continue

            collection_pages += 1
            new_urls = listing_parser.get_company_urls(result.content, result.final_url or col_url)
            added = [u for u in new_urls if u not in set(company_urls)]
            company_urls.extend(added)
            job.append_log(f"Found {len(new_urls)} company URLs (+{len(added)} new) on this page")

            next_col = listing_parser.get_next_page_url(result.content, result.final_url or col_url)
            if next_col and next_col not in collection_visited:
                collection_queue.append(next_col)
                job.append_log(f"Collection next page: {next_col}")

        job.append_log(f"Phase 1 complete — {len(company_urls)} unique company URLs")

        # --- Phase 2: fetch each company detail page ---
        all_leads = []
        detail_limit = max_pages * 10  # reasonable cap on detail pages
        for i, comp_url in enumerate(company_urls[:detail_limit]):
            if source.respect_robots and not fetcher.is_allowed_by_robots(comp_url):
                job.append_log(f"Skipped (robots.txt): {comp_url}")
                continue

            job.append_log(f"[{i+1}/{min(len(company_urls), detail_limit)}] {comp_url}")
            result = fetcher.fetch(comp_url)
            if not result.success:
                job.append_log(f"  Failed [{result.status_code}]: {result.error}")
                continue

            lead = detail_parser.parse(result.content, result.final_url or comp_url)
            if lead:
                all_leads.append(lead)
                job.append_log(f"  Extracted: {lead.company_name} | {lead.email} | {lead.phone}")
            else:
                job.append_log(f"  No usable data found")

        job.append_log(f"Phase 2 complete — {len(all_leads)} leads extracted")
        return all_leads

    def _execute_generic(self, job, source):
        fetcher = PageFetcher(delay=source.request_delay or 2.0)
        parser = get_parser(source.parsing_mode or "auto")
        config = source.get_selector_config()
        max_pages = source.max_pages or 5

        queue = [source.url]
        visited = set()
        all_leads = []
        pages_fetched = 0

        while queue and pages_fetched < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            # Robots.txt check
            if source.respect_robots and not fetcher.is_allowed_by_robots(url):
                job.append_log(f"Skipped (robots.txt disallowed): {url}")
                continue

            job.append_log(f"Fetching page {pages_fetched + 1}/{max_pages}: {url}")
            result = fetcher.fetch(url)

            if not result.success:
                job.append_log(f"Fetch failed [{result.status_code}]: {result.error}")
                continue

            pages_fetched += 1
            leads = parser.parse(result.content, result.final_url or url, config)
            job.append_log(f"Parsed {len(leads)} raw records")
            all_leads.extend(leads)

            # Pagination (listing mode)
            if source.source_type == "listing" and pages_fetched < max_pages:
                next_url = self._find_next_page(result.content, url)
                if next_url and next_url not in visited:
                    queue.append(next_url)
                    job.append_log(f"Next page found: {next_url}")

        job.append_log(f"Total raw records: {len(all_leads)} from {pages_fetched} pages")
        return all_leads

    def _save_leads(self, job, source, all_leads, auto_push_crm):
        """Normalize, deduplicate, persist, and optionally push to CRM."""
        job.total_found = len(all_leads)
        job.append_log(f"Processing {len(all_leads)} raw leads…")

        processed = failed = 0
        for parsed in all_leads:
            normalized = self.normalizer.normalize(parsed)
            if normalized is None:
                failed += 1
                continue

            try:
                record = self.env["lead.scraper.record"].create(
                    {
                        "job_id": job.id,
                        "source_id": source.id,
                        "normalized_status": "normalized",
                        "processing_status": "normalized",
                        **normalized,
                    }
                )
                self.deduplicator.check(record)

                if auto_push_crm and record.duplicate_status == "unique":
                    self.crm_mapper.create_lead(record)

                processed += 1
            except Exception as exc:
                _logger.exception("Record creation failed")
                failed += 1

        # Final counters
        records = self.env["lead.scraper.record"].search([("job_id", "=", job.id)])
        crm_created = len(records.filtered(lambda r: r.processing_status == "crm_created"))
        duplicates = len(records.filtered(lambda r: r.duplicate_status == "duplicate"))
        skipped = len(records.filtered(lambda r: r.processing_status == "skipped"))

        job.write(
            {
                "end_time": datetime.datetime.utcnow(),
                "status": "done",
                "total_found": len(all_leads),
                "total_processed": processed,
                "total_created": crm_created,
                "total_duplicates": duplicates,
                "total_skipped": skipped,
                "total_failed": failed,
            }
        )
        job.append_log(
            f"Done — processed: {processed} | CRM created: {crm_created} "
            f"| duplicates: {duplicates} | failed: {failed}"
        )

    def _find_next_page(self, html_content, current_url):
        """Heuristic: find a 'next page' link in HTML."""
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin

            soup = BeautifulSoup(html_content, "html.parser")
            for selector in (
                "a[rel='next']",
                "a.next",
                "a.pagination-next",
                "li.next a",
                ".next-page a",
                ".pager-next a",
            ):
                try:
                    el = soup.select_one(selector)
                    if el and el.get("href"):
                        return urljoin(current_url, el["href"])
                except Exception:
                    continue

            # Text-based fallback
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                if text in ("next", "next »", "»", "next page", "التالي"):
                    return urljoin(current_url, a["href"])
        except Exception:
            pass
        return None
