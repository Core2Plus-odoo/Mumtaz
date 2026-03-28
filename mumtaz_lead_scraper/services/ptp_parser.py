"""
Pakistan Trade Portal — Dedicated Scraper
==========================================
Strategy:
  1. Listing page (/collection/{category}) → extract all /company/ URLs
  2. Company detail page (/company/{slug}) → extract full contact info
  3. Decode Cloudflare-obfuscated emails via data-cfemail attribute

Usage in Odoo:
  - Source Type: Pakistan Trade Portal
  - URL: https://www.pakistantradeportal.gov.pk/collection/textiles
    (or any /collection/ page)
"""

import logging
import re
from urllib.parse import urljoin, urlparse

_logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from .parser import ParsedLead


def decode_cf_email(encoded):
    """
    Decode a Cloudflare-obfuscated email from a data-cfemail attribute.
    Algorithm: XOR each byte pair with the first byte.
    """
    try:
        r = int(encoded[:2], 16)
        return "".join(
            chr(int(encoded[i: i + 2], 16) ^ r)
            for i in range(2, len(encoded), 2)
        )
    except Exception:
        return ""


class PTPListingParser:
    """
    Parses a /collection/ page and returns all company profile URLs found.
    """

    COMPANY_RE = re.compile(r"/company/[a-z0-9\-]+", re.I)

    def get_company_urls(self, html_content, base_url):
        """Return a deduplicated list of absolute /company/ URLs."""
        if not BS4_AVAILABLE:
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        urls = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self.COMPANY_RE.search(href):
                full = urljoin(base_url, href).split("?")[0].split("#")[0]
                if full not in seen:
                    seen.add(full)
                    urls.append(full)

        return urls

    def get_next_page_url(self, html_content, current_url):
        """Find pagination 'next' link."""
        if not BS4_AVAILABLE:
            return None
        soup = BeautifulSoup(html_content, "html.parser")
        for sel in ("a[rel='next']", "a.next", "li.next a", ".pagination a.next"):
            try:
                el = soup.select_one(sel)
                if el and el.get("href"):
                    return urljoin(current_url, el["href"])
            except Exception:
                continue
        return None


class PTPDetailParser:
    """
    Parses a /company/{slug} page and returns a fully populated ParsedLead.
    """

    def parse(self, html_content, company_url):
        if not BS4_AVAILABLE:
            return None

        soup = BeautifulSoup(html_content, "html.parser")
        lead = ParsedLead()
        lead.source_url = company_url

        # ── Company name ──────────────────────────────────────────────
        # Try several common selectors for the page heading
        for sel in (
            "h1.store-title",
            ".store-name h1",
            ".page-header h1",
            ".vendor-name",
            ".shop-name",
            "h1",
        ):
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) > 1:
                    lead.company_name = text[:200]
                    break

        # Fallback: extract from URL slug
        if not lead.company_name:
            slug = urlparse(company_url).path.rstrip("/").split("/")[-1]
            # Convert slug like "crestline-smc-pvt-ltd-8170" → "Crestline Smc Pvt Ltd"
            name_part = re.sub(r"-\d+$", "", slug)
            lead.company_name = name_part.replace("-", " ").title()

        # ── Phone ─────────────────────────────────────────────────────
        phone_el = soup.select_one("li.store-phone")
        if phone_el:
            # Remove icon tags, get text
            for icon in phone_el.find_all("i"):
                icon.decompose()
            raw = phone_el.get_text(separator=" ", strip=True)
            lead.phone = raw[:50]

        # ── Email (Cloudflare-protected) ──────────────────────────────
        cf_el = soup.select_one("span.__cf_email__")
        if cf_el and cf_el.get("data-cfemail"):
            lead.email = decode_cf_email(cf_el["data-cfemail"])

        # Fallback: plain email in store-email block
        if not lead.email:
            email_block = soup.select_one("li.store-email")
            if email_block:
                text = email_block.get_text(strip=True)
                m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
                if m:
                    lead.email = m.group(0).lower()

        # ── Address ───────────────────────────────────────────────────
        addr_el = soup.select_one("li.store-address")
        if addr_el:
            for icon in addr_el.find_all("i"):
                icon.decompose()
            lead.city = addr_el.get_text(separator=", ", strip=True)[:200]

        # ── Website ───────────────────────────────────────────────────
        website_el = soup.select_one("li.store-website a, .store-website a")
        if website_el and website_el.get("href"):
            href = website_el["href"]
            if href.startswith("http") and "pakistantradeportal" not in href:
                lead.website = href[:500]

        # ── Country ───────────────────────────────────────────────────
        lead.country_name = "Pakistan"

        # ── Industry from URL context (passed via config) ─────────────
        # The collection category is passed in the raw_payload
        lead.raw_payload = {
            "source": "Pakistan Trade Portal",
            "company_url": company_url,
        }

        return lead if (lead.company_name or lead.email or lead.phone) else None
