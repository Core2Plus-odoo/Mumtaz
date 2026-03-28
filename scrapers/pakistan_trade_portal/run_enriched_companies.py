import csv
import re
import time
from typing import Iterable, List, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from config import BASE_URL, DELAY_SECONDS, HEADERS
from models import RawTradeRecord, ScoredTradeLead
from portal_selectors import (
    CITY_SELECTORS,
    COMPANY_CARD_SELECTORS,
    COMPANY_NAME_SELECTORS,
    SECTOR_SELECTORS,
)
from scoring import score_lead

OUTPUT_FILE = "enriched_company_leads.csv"
TIMEOUT_SECONDS = 30
MAX_FOLLOWUP_PAGES = 3


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def get_soup(url: str):
    return BeautifulSoup(fetch_html(url), "html.parser")


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


def _normalize_url(base_url: str, maybe_url: str) -> str:
    if not maybe_url:
        return ""
    return urljoin(base_url, maybe_url)


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

    for card_selector in COMPANY_CARD_SELECTORS:
        for card in soup.select(card_selector):
            company_name = _first_text(card, COMPANY_NAME_SELECTORS)
            if not _is_company_like(company_name):
                continue

            company_anchor = card.select_one("a[href]")
            company_url = _normalize_url(page_url, company_anchor["href"]) if company_anchor else ""

            records.append(
                RawTradeRecord(
                    company_name=company_name,
                    city=_first_text(card, CITY_SELECTORS),
                    sector=_first_text(card, SECTOR_SELECTORS),
                    source_url=page_url,
                    company_url=company_url,
                )
            )

        if records:
            return records

    for anchor in soup.select("a[href]"):
        anchor_text = _compact(anchor.get_text(" ", strip=True))
        if not _is_company_like(anchor_text):
            continue
        records.append(
            RawTradeRecord(
                company_name=anchor_text,
                source_url=page_url,
                company_url=_normalize_url(page_url, anchor.get("href", "")),
            )
        )

    return records


def _candidate_pages(soup) -> List[str]:
    candidates: List[str] = [BASE_URL]
    seen: Set[str] = {BASE_URL}
    keywords = ("supplier", "export", "company", "directory", "listing")

    for anchor in soup.select("a[href]"):
        href = _normalize_url(BASE_URL, anchor.get("href", ""))
        if not href or href in seen:
            continue
        if urlparse(href).netloc != urlparse(BASE_URL).netloc:
            continue

        text = _compact(anchor.get_text(" ", strip=True)).lower()
        if any(k in href.lower() or k in text for k in keywords):
            seen.add(href)
            candidates.append(href)

        if len(candidates) >= MAX_FOLLOWUP_PAGES + 1:
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


def scrape_enriched_companies() -> List[dict]:
    all_records: List[RawTradeRecord] = []

    try:
        soup = get_soup(BASE_URL)

        for page_url in _candidate_pages(soup):
            try:
                page_soup = get_soup(page_url)
                all_records.extend(_extract_records_from_soup(page_soup, page_url))
            except Exception as page_error:
                print(f"Warning: failed to scrape {page_url} ({page_error})")

    except Exception as exc:
        print(f"Warning: live scrape failed ({exc}). Proceeding with empty dataset.")

    enriched = []
    for raw in dedupe_records(all_records):
        scored = ScoredTradeLead(**raw.to_dict())
        score_lead(scored)
        enriched.append(scored.__dict__)
        if DELAY_SECONDS:
            time.sleep(min(DELAY_SECONDS, 0.2))

    return enriched


def write_csv(rows: List[dict], filename: str) -> None:
    fieldnames = list(ScoredTradeLead().__dict__.keys())
    with open(filename, "w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    rows = scrape_enriched_companies()
    write_csv(rows, OUTPUT_FILE)
    print(f"Source host: {urlparse(BASE_URL).netloc}")
    print(f"Saved {len(rows)} enriched company leads to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
