import csv
import re
import ssl
import time
from html.parser import HTMLParser
from typing import Iterable, List
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    import requests
except Exception:  # pragma: no cover - dependency fallback
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - dependency fallback
    BeautifulSoup = None

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


class AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors = []
        self._current_href = ""
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href", "")
            self._current_text = []

    def handle_data(self, data):
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current_href:
            self.anchors.append(("".join(self._current_text), self._current_href))
            self._current_href = ""
            self._current_text = []


def _download_html(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()) as r:
        return r.read().decode("utf-8", errors="replace")


def get_soup(url: str):
    if requests is not None and BeautifulSoup is not None:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    if BeautifulSoup is not None:
        html = _download_html(url)
        return BeautifulSoup(html, "html.parser")

    return None


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


def _is_company_like(anchor_text: str) -> bool:
    text = _compact(anchor_text)
    if len(text) < 4:
        return False
    if text.lower() in {"home", "about", "contact", "login", "register"}:
        return False
    hints = ("ltd", "limited", "traders", "industries", "enterprise", "co", "company")
    return any(h in text.lower() for h in hints) or len(text.split()) >= 2


def _extract_from_cards(soup, page_url: str) -> List[RawTradeRecord]:
    records: List[RawTradeRecord] = []
    for card_selector in COMPANY_CARD_SELECTORS:
        cards = soup.select(card_selector)
        for card in cards:
            company_name = _first_text(card, COMPANY_NAME_SELECTORS)
            if not _is_company_like(company_name):
                continue

            company_anchor = card.select_one("a[href]")
            company_url = _normalize_url(page_url, company_anchor["href"]) if company_anchor else ""

            record = RawTradeRecord(
                company_name=company_name,
                city=_first_text(card, CITY_SELECTORS),
                sector=_first_text(card, SECTOR_SELECTORS),
                source_url=page_url,
                company_url=company_url,
            )
            records.append(record)

        if records:
            break
    return records


def _extract_from_anchors_bs4(soup, page_url: str) -> List[RawTradeRecord]:
    records: List[RawTradeRecord] = []
    for a in soup.select("a[href]"):
        text = _compact(a.get_text(" ", strip=True))
        if not _is_company_like(text):
            continue
        records.append(
            RawTradeRecord(
                company_name=text,
                source_url=page_url,
                company_url=_normalize_url(page_url, a.get("href", "")),
            )
        )
    return records


def _extract_from_anchors_html(page_url: str) -> List[RawTradeRecord]:
    parser = AnchorCollector()
    parser.feed(_download_html(page_url))
    records: List[RawTradeRecord] = []
    for text, href in parser.anchors:
        text = _compact(text)
        if not _is_company_like(text):
            continue
        records.append(
            RawTradeRecord(
                company_name=text,
                source_url=page_url,
                company_url=_normalize_url(page_url, href),
            )
        )
    return records


def dedupe_records(records: List[RawTradeRecord]) -> List[RawTradeRecord]:
    seen = set()
    deduped = []
    for record in records:
        key = (record.company_name.lower().strip(), record.company_url.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def scrape_enriched_companies() -> List[dict]:
    records: List[RawTradeRecord] = []
    try:
        soup = get_soup(BASE_URL)
        if soup is not None:
            records = _extract_from_cards(soup, BASE_URL)
            if not records:
                records = _extract_from_anchors_bs4(soup, BASE_URL)
        else:
            records = _extract_from_anchors_html(BASE_URL)
    except Exception as exc:
        print(f"Warning: live scrape failed ({exc}). Proceeding with empty dataset.")

    enriched = []
    for raw in dedupe_records(records):
        scored = ScoredTradeLead(**raw.to_dict())
        scored = score_lead(scored)
        enriched.append(scored.__dict__)
        if DELAY_SECONDS:
            time.sleep(min(DELAY_SECONDS, 0.2))
    return enriched


def write_csv(rows: List[dict], filename: str) -> None:
    fieldnames = list(ScoredTradeLead().__dict__.keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def main() -> None:
    rows = scrape_enriched_companies()
    write_csv(rows, OUTPUT_FILE)
    host = urlparse(BASE_URL).netloc
    print(f"Source host: {host}")
    print(f"Saved {len(rows)} enriched company leads to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
