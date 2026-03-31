import argparse
import csv
import logging
import re
import time
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    BACKOFF_FACTOR,
    BASE_URL,
    DELAY_SECONDS,
    HEADERS,
    MAX_PAGES,
    MAX_RETRIES,
    ODOO_DB,
    ODOO_PASSWORD,
    ODOO_URL,
    ODOO_USERNAME,
    TIMEOUT_SECONDS,
)
from models import RawTradeRecord, ScoredTradeLead
from odoo_push import OdooPushError, push_leads_to_odoo
from portal_selectors import (
    CITY_SELECTORS,
    COMPANY_CARD_SELECTORS,
    COMPANY_NAME_SELECTORS,
    SECTOR_SELECTORS,
)
from scoring import score_lead

OUTPUT_FILE = "enriched_company_leads.csv"
_LOGGER = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_REGEX = re.compile(r"(?:(?:\+|00)\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,5}")

    return candidate.rstrip("/") + "/"

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _normalize_url(raw_url: str) -> str:
    candidate = (raw_url or "").strip()
    if not candidate:
        raise ValueError("Website URL is required")

    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {raw_url}")

    return candidate.rstrip("/") + "/"


def _build_session() -> requests.Session:
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[403, 408, 429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update(HEADERS)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_html(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True)
    _LOGGER.info(
        "fetch status=%s requested=%s final=%s",
        response.status_code,
        url,
        response.url,
    )
    return response


def get_soup(session: requests.Session, url: str):
    response = fetch_html(session, url)
    if response.status_code >= 400:
        raise requests.HTTPError(f"HTTP {response.status_code} for {response.url}", response=response)
    return BeautifulSoup(response.text, "html.parser"), response


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _first_text(node, selectors: Iterable[str]) -> str:
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            text = _compact(found.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _normalize_link(base_url: str, maybe_url: str) -> str:
    if not maybe_url:
        return ""
    return urljoin(base_url, maybe_url)


def _extract_emails(text: str) -> str:
    return ", ".join(sorted(set(EMAIL_REGEX.findall(text or ""))))


def _extract_phones(text: str) -> str:
    found = []
    for item in PHONE_REGEX.findall(text or ""):
        number = _compact(item)
        if len(re.sub(r"\D", "", number)) >= 7:
            found.append(number)
    return ", ".join(sorted(set(found)))


def _extract_social_links(soup, page_url: str) -> str:
    social_domains = ("linkedin.com", "facebook.com", "twitter.com", "instagram.com")
    links = []
    for anchor in soup.select("a[href]"):
        href = _normalize_link(page_url, anchor.get("href", ""))
        if any(domain in href.lower() for domain in social_domains):
            links.append(href)
    return ", ".join(sorted(set(links)))


def _extract_company_name(soup, fallback_url: str) -> str:
    site_name = soup.select_one("meta[property='og:site_name']")
    if site_name and site_name.get("content"):
        return _compact(site_name["content"])

    for selector in ("h1", ".logo", ".site-title", "title"):
        node = soup.select_one(selector)
        if node:
            text = _compact(node.get_text(" ", strip=True))
            if text and len(text) >= 3:
                return text[:140]

    return urlparse(fallback_url).netloc


def _extract_description(soup) -> str:
    meta_description = soup.select_one("meta[name='description']")
    if meta_description and meta_description.get("content"):
        return _compact(meta_description["content"])

    og_description = soup.select_one("meta[property='og:description']")
    if og_description and og_description.get("content"):
        return _compact(og_description["content"])

    for selector in ("main p", "article p", ".about p", "#about p", "p"):
        node = soup.select_one(selector)
        if node:
            text = _compact(node.get_text(" ", strip=True))
            if len(text) >= 50:
                return text[:800]
    return ""


def _extract_address(soup) -> str:
    for selector in ("address", ".address", "[class*='address']", "[id*='address']"):
        node = soup.select_one(selector)
        if node:
            text = _compact(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _detect_js_heavy_page(soup) -> bool:
    text_len = len(_compact(soup.get_text(" ", strip=True)))
    scripts = len(soup.select("script"))
    return scripts >= 20 and text_len < 300


def _extract_page_lead(soup, page_url: str, base_url: str) -> Optional[RawTradeRecord]:
    full_text = soup.get_text(" ", strip=True)
    company_name = _extract_company_name(soup, base_url)
    emails = _extract_emails(full_text)
    phones = _extract_phones(full_text)
    description = _extract_description(soup)

    if not any([company_name, emails, phones, description]):
        return None

    return RawTradeRecord(
        company_name=company_name,
        source_url=page_url,
        company_url=base_url,
        website=base_url,
        contact_email=emails,
        contact_phone=phones,
        address=_extract_address(soup),
        description=description,
        social_links=_extract_social_links(soup, page_url),
        has_contact_form=bool(soup.select_one("form input[type='email'], form textarea")),
        scrape_status="parsed",
    )


def _is_company_like(text: str) -> bool:
    text = _compact(text)
    if len(text) < 4:
        return False

    blocked = {"home", "about", "contact", "login", "register", "read more", "details"}
    if text.lower() in blocked:
        return False

    business_hints = (
        "ltd",
        "limited",
        "traders",
        "industries",
        "enterprise",
        "company",
        "corp",
        "pvt",
    )
    return any(hint in text.lower() for hint in business_hints) or len(text.split()) >= 3


def _extract_records_from_soup(soup, page_url: str) -> List[RawTradeRecord]:
    records: List[RawTradeRecord] = []
    full_text = soup.get_text(" ", strip=True)

    for card_selector in COMPANY_CARD_SELECTORS:
        for card in soup.select(card_selector):
            company_name = _first_text(card, COMPANY_NAME_SELECTORS)
            if not _is_company_like(company_name):
                continue

            company_anchor = card.select_one("a[href]")
            company_url = _normalize_link(page_url, company_anchor["href"]) if company_anchor else ""
            snippet = card.get_text(" ", strip=True)

            records.append(
                RawTradeRecord(
                    company_name=company_name,
                    city=_first_text(card, CITY_SELECTORS),
                    sector=_first_text(card, SECTOR_SELECTORS),
                    source_url=page_url,
                    company_url=company_url,
                    website=company_url,
                    contact_email=_extract_emails(snippet),
                    contact_phone=_extract_phones(snippet),
                    address=_extract_address(card) or _extract_address(soup),
                    description=_compact(snippet)[:600],
                    social_links=_extract_social_links(soup, page_url),
                    has_contact_form=bool(soup.select_one("form input[type='email'], form textarea")),
                    scrape_status="parsed",
                )
            )

        if records:
            return records

    for anchor in soup.select("a[href]"):
        anchor_text = _compact(anchor.get_text(" ", strip=True))
        if not _is_company_like(anchor_text):
            continue
        company_url = _normalize_link(page_url, anchor.get("href", ""))
        records.append(
            RawTradeRecord(
                company_name=anchor_text,
                source_url=page_url,
                company_url=company_url,
                website=company_url,
                contact_email=_extract_emails(full_text),
                contact_phone=_extract_phones(full_text),
                address=_extract_address(soup),
                description=_extract_description(soup),
                social_links=_extract_social_links(soup, page_url),
                has_contact_form=bool(soup.select_one("form input[type='email'], form textarea")),
                scrape_status="parsed",
            )
        )

    return records


def _candidate_pages(soup, base_url: str) -> List[str]:
    candidates: List[str] = [base_url]
    seen: Set[str] = {base_url}
    keywords = (
        "supplier",
        "export",
        "company",
        "directory",
        "listing",
        "about",
        "contact",
        "team",
        "services",
        "products",
    )

    for anchor in soup.select("a[href]"):
        href = _normalize_link(base_url, anchor.get("href", ""))
        if not href or href in seen:
            continue
        if urlparse(href).netloc != urlparse(base_url).netloc:
            continue

        text = _compact(anchor.get_text(" ", strip=True)).lower()
        if any(k in href.lower() or k in text for k in keywords):
            seen.add(href)
            candidates.append(href)

        if len(candidates) >= MAX_PAGES:
            break

    return candidates


def dedupe_records(records: List[RawTradeRecord]) -> List[RawTradeRecord]:
    seen = set()
    unique = []
    for record in records:
        key = (record.company_name.lower().strip(), record.company_url.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _valid_for_lead(record: RawTradeRecord) -> bool:
    return bool(
        record.company_name
        or record.contact_email
        or record.contact_phone
        or record.description
    )


def _status_template(source_url: str) -> Dict[str, str]:
    return {
        "source_url": source_url,
        "scrape_status": "failed",
        "scrape_error": "",
    }


def scrape_enriched_companies(target_url: str) -> List[dict]:
    normalized_url = _normalize_url(target_url)
    _LOGGER.info("scrape_start url=%s", normalized_url)

    session = _build_session()
    all_records: List[RawTradeRecord] = []

    try:
        soup, response = get_soup(session, normalized_url)
        if response.status_code in (401, 403):
            _LOGGER.warning("site_blocking_detected status=%s url=%s", response.status_code, response.url)

        if _detect_js_heavy_page(soup):
            _LOGGER.warning("js_heavy_page_detected url=%s", normalized_url)

        for page_url in _candidate_pages(soup, normalized_url):
            try:
                page_soup, _ = get_soup(session, page_url)
                page_lead = _extract_page_lead(page_soup, page_url, normalized_url)
                if page_lead:
                    all_records.append(page_lead)
                extracted = _extract_records_from_soup(page_soup, page_url)
                _LOGGER.info("parsed_page url=%s records=%s", page_url, len(extracted))
                all_records.extend(extracted)
            except Exception as page_error:
                _LOGGER.exception("page_parse_failed url=%s error=%s", page_url, page_error)

    except Exception as exc:
        _LOGGER.exception("scrape_failed url=%s error=%s", normalized_url, exc)
        failed = _status_template(normalized_url)
        failed["scrape_error"] = str(exc)
        return [failed]

    enriched = []
    unique_records = dedupe_records(all_records)
    _LOGGER.info("dedupe_complete before=%s after=%s", len(all_records), len(unique_records))

    for raw in unique_records:
        if not _valid_for_lead(raw):
            _LOGGER.debug("discarding_record_missing_minimum_payload source=%s", raw.source_url)
            continue
        scored = ScoredTradeLead(**raw.to_dict())
        if scored.scrape_status == "draft":
            scored.scrape_status = "parsed"
        score_lead(scored)
        enriched.append(scored.__dict__)
        if DELAY_SECONDS:
            time.sleep(min(DELAY_SECONDS, 0.2))

    _LOGGER.info("scrape_complete url=%s leads=%s", normalized_url, len(enriched))
    return enriched


def write_csv(rows: List[dict], filename: str) -> None:
    fieldnames = list(ScoredTradeLead().__dict__.keys())
    with open(filename, "w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def push_rows_to_odoo(rows: List[dict]) -> None:
    config = {
        "url": ODOO_URL,
        "db": ODOO_DB,
        "username": ODOO_USERNAME,
        "password": ODOO_PASSWORD,
    }
    try:
        created_ids = push_leads_to_odoo(rows, config)
        for row in rows:
            if row.get("scrape_status") != "failed":
                row["scrape_status"] = "lead_created"
        _LOGGER.info("odoo_push_complete created=%s", len(created_ids))
    except OdooPushError as exc:
        for row in rows:
            row["scrape_status"] = "failed"
            row["scrape_error"] = str(exc)
        _LOGGER.error("odoo_push_configuration_error error=%s", exc)
    except Exception as exc:
        for row in rows:
            row["scrape_status"] = "failed"
            row["scrape_error"] = str(exc)
        _LOGGER.exception("odoo_push_failed error=%s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape company leads and optionally push to Odoo CRM")
    parser.add_argument("--url", default=BASE_URL, help="Website URL to scrape")
    parser.add_argument("--output", default=OUTPUT_FILE, help="CSV output path")
    parser.add_argument("--push-odoo", action="store_true", help="Push extracted leads to Odoo CRM")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    rows = scrape_enriched_companies(args.url)
    write_csv(rows, args.output)

    if args.push_odoo:
        push_rows_to_odoo(rows)

    print(f"Source host: {urlparse(_normalize_url(args.url)).netloc}")
    print(f"Saved {len(rows)} enriched company leads to {args.output}")


if __name__ == "__main__":
    main()
