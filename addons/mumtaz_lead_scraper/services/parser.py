"""
Lead Parsers
============
Strategies for extracting structured lead data from raw HTML/JSON.

Three parsers:
- AutoParser   — heuristic extraction from any HTML page
- CSSParser    — CSS-selector driven extraction (config required)
- JSONParser   — JSON path driven extraction (config required)

Use get_parser(mode) to get the right instance.
"""

import json
import logging
import re
from urllib.parse import urljoin, urlparse

_logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    _logger.warning("beautifulsoup4 not installed — pip install beautifulsoup4")


class ParsedLead:
    """Intermediate representation of a scraped lead before normalization."""

    __slots__ = [
        "company_name", "contact_name", "email", "phone", "website",
        "city", "country_name", "industry", "source_url", "description", "raw_payload",
    ]

    def __init__(self):
        for attr in self.__slots__:
            setattr(self, attr, "" if attr != "raw_payload" else {})

    def to_dict(self):
        d = {k: getattr(self, k) for k in self.__slots__}
        d["raw_payload"] = json.dumps(d["raw_payload"]) if isinstance(d["raw_payload"], dict) else d["raw_payload"]
        return d


# ---------------------------------------------------------------------------
# Auto Parser (heuristic)
# ---------------------------------------------------------------------------

class AutoParser:
    """
    Heuristic parser that finds contact info from any HTML page.
    Looks for email/phone in block-level containers (article, div.card, etc.)
    and falls back to full-page scan.
    """

    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)\.]{7,20}")
    CONTAINER_RE = re.compile(
        r"(card|result|item|listing|company|business|contact|lead|entry|profile)",
        re.I,
    )

    def parse(self, html_content, source_url, config=None):
        if not BS4_AVAILABLE:
            _logger.error("bs4 not installed — cannot parse")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        leads = []

        containers = soup.find_all(
            ["article", "div", "li", "section"],
            class_=self.CONTAINER_RE,
            limit=200,
        )

        if containers:
            for block in containers:
                lead = self._from_block(block, source_url)
                if lead and (lead.email or lead.phone or lead.company_name):
                    leads.append(lead)

        if not leads:
            lead = self._from_page(soup, source_url)
            if lead:
                leads.append(lead)

        return leads

    def _from_block(self, el, source_url):
        lead = ParsedLead()
        lead.source_url = source_url
        text = el.get_text(separator=" ", strip=True)

        emails = self.EMAIL_RE.findall(text)
        if emails:
            lead.email = emails[0].lower()

        phones = self.PHONE_RE.findall(text)
        if phones:
            lead.phone = phones[0].strip()

        for tag in ("h1", "h2", "h3", "h4", "strong", "b"):
            found = el.find(tag)
            if found and found.get_text(strip=True):
                lead.company_name = found.get_text(strip=True)[:200]
                break

        for a in el.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and urlparse(href).netloc != urlparse(source_url).netloc:
                lead.website = href[:500]
                break

        lead.description = text[:500]
        lead.raw_payload = {"snippet": str(el)[:800]}
        return lead

    def _from_page(self, soup, source_url):
        text = soup.get_text(separator=" ", strip=True)
        emails = self.EMAIL_RE.findall(text)
        phones = self.PHONE_RE.findall(text)

        if not emails and not phones:
            return None

        lead = ParsedLead()
        lead.source_url = source_url
        if emails:
            lead.email = emails[0].lower()
        if phones:
            lead.phone = phones[0].strip()

        title = soup.find("title")
        if title:
            lead.company_name = title.get_text(strip=True)[:200]

        lead.description = text[:500]
        lead.raw_payload = {"all_emails": emails[:5], "all_phones": phones[:5]}
        return lead


# ---------------------------------------------------------------------------
# CSS Selector Parser
# ---------------------------------------------------------------------------

class CSSParser:
    """
    CSS-selector driven parser.

    Config JSON example:
    {
        "container": ".listing-item",
        "company_name": ".name",
        "email": ".email",
        "phone": ".phone",
        "website": "a.site@href",    <- @attr suffix to get attribute value
        "city": ".location .city",
        "country_name": ".country",
        "industry": ".category",
        "contact_name": ".contact",
        "description": ".summary"
    }
    """

    FIELDS = [
        "company_name", "contact_name", "email", "phone",
        "website", "city", "country_name", "industry", "description",
    ]

    def parse(self, html_content, source_url, config=None):
        if not BS4_AVAILABLE:
            return []

        config = config or {}
        container_sel = config.get("container")

        if not container_sel:
            return AutoParser().parse(html_content, source_url, config)

        soup = BeautifulSoup(html_content, "html.parser")
        leads = []

        for container in soup.select(container_sel):
            lead = ParsedLead()
            lead.source_url = source_url

            for field in self.FIELDS:
                sel = config.get(field, "")
                if not sel:
                    continue
                attr = None
                if "@" in sel:
                    sel, attr = sel.rsplit("@", 1)
                el = container.select_one(sel)
                if el:
                    val = el.get(attr, "").strip() if attr else el.get_text(strip=True)
                    max_len = 1000 if field == "description" else 200
                    setattr(lead, field, val[:max_len])

            lead.raw_payload = {"config": config}
            if any([lead.company_name, lead.email, lead.phone]):
                leads.append(lead)

        return leads


# ---------------------------------------------------------------------------
# JSON / API Parser
# ---------------------------------------------------------------------------

class JSONParser:
    """
    JSON path parser for API endpoints.

    Config JSON example:
    {
        "root_path": "data.results",
        "company_name": "name",
        "email": "contact.email",
        "phone": "contact.phone",
        "city": "address.city",
        "country_name": "address.country",
        "website": "url",
        "industry": "sector"
    }
    """

    FIELDS = [
        "company_name", "contact_name", "email", "phone",
        "website", "city", "country_name", "industry", "description",
    ]

    def parse(self, html_content, source_url, config=None):
        config = config or {}
        leads = []

        try:
            data = json.loads(html_content)
        except json.JSONDecodeError:
            _logger.warning("JSON decode failed for %s", source_url)
            return leads

        root_path = config.get("root_path", "")
        if root_path:
            for key in root_path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])
                else:
                    break

        if not isinstance(data, list):
            data = [data]

        for item in data:
            lead = ParsedLead()
            lead.source_url = source_url

            for field in self.FIELDS:
                path = config.get(field, "")
                if not path:
                    continue
                val = self._nested_get(item, path)
                if val is not None:
                    max_len = 1000 if field == "description" else 200
                    setattr(lead, field, str(val)[:max_len])

            lead.raw_payload = item if isinstance(item, dict) else {}
            if any([lead.company_name, lead.email, lead.phone]):
                leads.append(lead)

        return leads

    @staticmethod
    def _nested_get(data, path):
        """Resolve dot-notation path in a nested dict."""
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_parser(parsing_mode):
    return {"auto": AutoParser, "css": CSSParser, "json": JSONParser}.get(
        parsing_mode, AutoParser
    )()
