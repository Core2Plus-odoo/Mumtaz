"""
DIFC Public Register — Dedicated Scraper
=========================================
The DIFC Public Register (https://www.difc.com/business/public-register) is a
Next.js SPA backed by Sitecore XM Cloud.

Approach (in priority order):

  1. Parse __NEXT_DATA__ embedded JSON in the page HTML
     Every Next.js page embeds its initial props in
     <script id="__NEXT_DATA__">{"props":{"pageProps":{...}}}</script>
     The public register data is often in pageProps.

  2. Probe API endpoints found inside __NEXT_DATA__
     The config / env section often contains the real API base URL.

  3. POST /api/handleRequest with browser headers + CSRF token extracted
     from the page HTML (meta[name=csrf-token] or similar).

  4. Direct HTML pagination scrape (BeautifulSoup fallback)
     If the page server-renders a table of companies.

Usage in Odoo:
  - Source Type  : DIFC Public Register
  - URL          : https://www.difc.com/business/public-register
  - Max Pages    : controls pagination depth (default 20)
  - request_delay: seconds between requests (default 2.0)
"""

import json
import logging
import re
import time
from urllib.parse import urlparse, urljoin, urlencode

_logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from .parser import ParsedLead

# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_PAGE_SIZE = 20

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_JSON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Keys to walk in __NEXT_DATA__ searching for a list of companies
_COMPANY_LIST_KEYS = (
    "companies", "entities", "results", "records", "items",
    "data", "list", "register", "publicRegister", "companyList",
)

# Candidate POST action names for /api/handleRequest (tried last)
_POST_ACTIONS = [
    "request-company-details",
    "difc/request-company-details",
    "getPublicRegister",
    "publicRegister",
    "difc/publicRegister",
    "searchCompanies",
    "difc/searchCompanies",
]

# Response envelope unwrappers
_ARRAY_PATHS = [
    lambda d: d.get("data", {}).get("results") if isinstance(d.get("data"), dict) else None,
    lambda d: d.get("data") if isinstance(d.get("data"), list) else None,
    lambda d: d.get("results") if isinstance(d.get("results"), list) else None,
    lambda d: d.get("Items") if isinstance(d.get("Items"), list) else None,
    lambda d: d.get("items") if isinstance(d.get("items"), list) else None,
    lambda d: d.get("companies") if isinstance(d.get("companies"), list) else None,
    lambda d: d.get("entities") if isinstance(d.get("entities"), list) else None,
    lambda d: d.get("records") if isinstance(d.get("records"), list) else None,
]

_TOTAL_KEYS = ("totalCount", "total_count", "TotalCount", "Total",
               "total", "count", "Count", "totalResults", "totalRecords")

# Field candidates for ParsedLead mapping
_NAME_KEYS   = ("companyName", "company_name", "name", "Name", "entityName",
                "legalName", "LegalName", "title", "Title")
_TYPE_KEYS   = ("licenseType", "license_type", "type", "Type", "entityType",
                "category", "Category", "companyType", "regulatoryStatus")
_STATUS_KEYS = ("status", "Status", "licenseStatus", "entityStatus",
                "state", "State", "registrationStatus")
_WEB_KEYS    = ("website", "Website", "url", "webAddress", "web", "websiteUrl")
_EMAIL_KEYS  = ("email", "Email", "emailAddress", "contactEmail", "email_address")
_PHONE_KEYS  = ("phone", "Phone", "phoneNumber", "contactPhone",
                "telephone", "Telephone", "mobile")
_ADDR_KEYS   = ("address", "Address", "registeredAddress", "officeAddress",
                "location", "Location", "physicalAddress")


# ── Main parser class ─────────────────────────────────────────────────────────

class DIFCRegisterParser:
    """
    Fetches DIFC Public Register data.  Tries multiple strategies in order,
    locks onto the first that works, and reuses it for pagination.
    """

    def __init__(self, base_url, delay=2.0, timeout=25):
        parsed = urlparse(base_url)
        self._origin = f"{parsed.scheme}://{parsed.netloc}"
        self._register_url = base_url
        self._delay = max(delay, 1.0)
        self._timeout = timeout
        self._session = None
        self._last_req = 0.0
        self._page_html = None        # cached HTML of the register page
        self._next_data = None        # parsed __NEXT_DATA__ JSON
        self._api_base = None         # discovered API base URL
        self._csrf_token = None       # CSRF token if found
        self._strategy = None         # locked strategy once discovered

    # ── Session helpers ───────────────────────────────────────────────────────

    def _sess(self):
        if self._session is None:
            if not REQUESTS_AVAILABLE:
                raise RuntimeError("requests library not installed")
            self._session = requests.Session()
            self._session.headers.update(_BROWSER_HEADERS)
        return self._session

    def _rate_limit(self):
        elapsed = time.time() - self._last_req
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)

    # ── Page fetch & __NEXT_DATA__ extraction ─────────────────────────────────

    def _fetch_page_html(self):
        """Fetch the public register HTML page and cache it."""
        if self._page_html is not None:
            return self._page_html
        self._rate_limit()
        try:
            resp = self._sess().get(self._register_url, timeout=self._timeout)
            self._last_req = time.time()
            _logger.info("DIFC page fetch: GET %s → %s", self._register_url, resp.status_code)
            if resp.status_code == 200:
                self._page_html = resp.text
                self._extract_next_data(resp.text)
                self._extract_csrf(resp.text)
            else:
                _logger.warning("DIFC page fetch failed: HTTP %s", resp.status_code)
                self._page_html = ""
        except Exception as exc:
            _logger.warning("DIFC page fetch error: %s", exc)
            self._page_html = ""
        return self._page_html

    def _extract_next_data(self, html):
        """Parse <script id="__NEXT_DATA__"> JSON from the page."""
        m = re.search(
            r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if not m:
            _logger.warning("DIFC: __NEXT_DATA__ not found in page HTML")
            return
        try:
            self._next_data = json.loads(m.group(1))
            _logger.info(
                "DIFC: __NEXT_DATA__ parsed — top-level keys: %s",
                list(self._next_data.keys())
            )
            # Look for API base URL in runtimeConfig or env
            self._discover_api_base(self._next_data)
        except (json.JSONDecodeError, ValueError) as exc:
            _logger.warning("DIFC: __NEXT_DATA__ JSON parse error: %s", exc)

    def _discover_api_base(self, next_data):
        """Scan __NEXT_DATA__ for an API base URL."""
        cfg = next_data.get("runtimeConfig") or next_data.get("publicRuntimeConfig") or {}
        for key in ("apiUrl", "api_url", "API_URL", "publicApiUrl", "backendUrl",
                    "sitecoreApiHost", "apiHost", "baseUrl"):
            val = cfg.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                self._api_base = val.rstrip("/")
                _logger.info("DIFC: discovered API base from runtimeConfig.%s = %s", key, val)
                return

        # Also search env vars embedded in __NEXT_DATA__
        env = next_data.get("env") or {}
        for key, val in env.items():
            if "api" in key.lower() and isinstance(val, str) and val.startswith("http"):
                self._api_base = val.rstrip("/")
                _logger.info("DIFC: discovered API base from env.%s = %s", key, val)
                return

    def _extract_csrf(self, html):
        """Look for CSRF token in meta tags or cookies."""
        m = re.search(
            r'<meta[^>]+name=["\']csrf-?token["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.I
        )
        if m:
            self._csrf_token = m.group(1)
            _logger.info("DIFC: found CSRF token in meta tag")
            return
        # Check cookies set during the page fetch
        for cookie in self._sess().cookies:
            if "csrf" in cookie.name.lower() or "xsrf" in cookie.name.lower():
                self._csrf_token = cookie.value
                _logger.info("DIFC: found CSRF token in cookie: %s", cookie.name)
                return

    # ── Strategy: extract from __NEXT_DATA__ directly ────────────────────────

    def _leads_from_next_data(self):
        """
        Try to extract companies directly from the embedded __NEXT_DATA__ props.
        Returns list of ParsedLead or None if not found.
        """
        if not self._next_data:
            return None

        # Walk pageProps looking for a list of companies
        page_props = (
            self._next_data.get("props", {}).get("pageProps", {})
        )
        _logger.info(
            "DIFC __NEXT_DATA__ pageProps keys: %s",
            list(page_props.keys()) if isinstance(page_props, dict) else type(page_props)
        )

        # Search recursively up to depth 4
        items = self._find_company_list(page_props, depth=0, max_depth=4)
        if items:
            _logger.info("DIFC: extracted %d companies from __NEXT_DATA__", len(items))
            return items
        return None

    def _find_company_list(self, obj, depth, max_depth):
        """Recursively search for a list that looks like company records."""
        if depth > max_depth:
            return None
        if isinstance(obj, list):
            if len(obj) > 0 and isinstance(obj[0], dict):
                # Check if first item looks like a company
                first = obj[0]
                if any(k in first for k in ("companyName", "name", "Name",
                                             "entityName", "licenseNumber")):
                    return obj
        if isinstance(obj, dict):
            # Try known key names first
            for key in _COMPANY_LIST_KEYS:
                val = obj.get(key)
                if isinstance(val, list) and len(val) > 0:
                    result = self._find_company_list(val, depth + 1, max_depth)
                    if result:
                        return result
            # Recurse into all values
            for val in obj.values():
                if isinstance(val, (dict, list)):
                    result = self._find_company_list(val, depth + 1, max_depth)
                    if result:
                        return result
        return None

    # ── Strategy: JSON API ────────────────────────────────────────────────────

    def _build_json_headers(self):
        h = dict(_JSON_HEADERS)
        h["Referer"] = self._register_url
        h["Origin"] = self._origin
        if self._csrf_token:
            h["X-CSRF-Token"] = self._csrf_token
            h["X-XSRF-Token"] = self._csrf_token
        return h

    def _api_get(self, url, params):
        self._rate_limit()
        try:
            resp = self._sess().get(
                url, params=params, headers=self._build_json_headers(),
                timeout=self._timeout
            )
            self._last_req = time.time()
            snippet = resp.text[:300].replace("\n", " ")
            if resp.status_code not in (200, 201):
                return False, None, resp.status_code, f"HTTP {resp.status_code}", snippet
            try:
                return True, resp.json(), resp.status_code, "", snippet
            except ValueError:
                return False, None, resp.status_code, "Not JSON", snippet
        except requests.exceptions.Timeout:
            return False, None, 0, "Timeout", ""
        except Exception as exc:
            return False, None, 0, str(exc), ""

    def _api_post(self, url, body):
        self._rate_limit()
        try:
            resp = self._sess().post(
                url, json=body, headers=self._build_json_headers(),
                timeout=self._timeout
            )
            self._last_req = time.time()
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", "5")))
                resp = self._sess().post(
                    url, json=body, headers=self._build_json_headers(),
                    timeout=self._timeout
                )
                self._last_req = time.time()
            snippet = resp.text[:300].replace("\n", " ")
            if resp.status_code not in (200, 201):
                return False, None, resp.status_code, f"HTTP {resp.status_code}", snippet
            try:
                return True, resp.json(), resp.status_code, "", snippet
            except ValueError:
                return False, None, resp.status_code, "Not JSON", snippet
        except requests.exceptions.Timeout:
            return False, None, 0, "Timeout", ""
        except Exception as exc:
            return False, None, 0, str(exc), ""

    # ── Next.js JSON page route ───────────────────────────────────────────────

    def _fetch_next_json_page(self, page_number, page_size):
        """
        Try Next.js built-in JSON data endpoint:
        GET /_next/data/{buildId}/business/public-register.json
        """
        if not self._next_data:
            return None, ""
        build_id = self._next_data.get("buildId", "")
        if not build_id:
            return None, "no buildId in __NEXT_DATA__"
        url = f"{self._origin}/_next/data/{build_id}/business/public-register.json"
        params = {"page": page_number, "pageSize": page_size, "companyName": ""}
        ok, data, status, err, snippet = self._api_get(url, params)
        if not ok:
            return None, f"Next.js JSON route: {err} | {snippet[:120]}"
        items = self._extract_items(data)
        if items is None:
            # Log the structure so we know what keys are available
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            _logger.info("DIFC Next.js JSON route keys: %s | snippet: %s", keys, snippet[:200])
            # Try to find companies in the response
            items = self._find_company_list(data, 0, 5) or []
        return items, ""

    # ── Public entry point ────────────────────────────────────────────────────

    def fetch_page(self, page_number, page_size=_DEFAULT_PAGE_SIZE):
        """
        Fetch one page.  Returns (items, total, error_str).
        """
        # Always fetch the HTML on page 1
        if page_number == 1:
            html = self._fetch_page_html()
            if not html:
                return [], 0, "Failed to fetch public register page HTML"

        # ── Use locked strategy for page > 1 ─────────────────────────────
        if self._strategy is not None and page_number > 1:
            return self._fetch_with_strategy(self._strategy, page_number, page_size)

        errors = []

        # ── Strategy 1: extract from __NEXT_DATA__ (page 1 only) ─────────
        if page_number == 1 and self._next_data:
            items = self._leads_from_next_data()
            if items is not None:
                self._strategy = ("next_data", None)
                _logger.info("DIFC: using __NEXT_DATA__ strategy")
                return items, len(items), ""
            errors.append("__NEXT_DATA__: pageProps contained no company list")
            _logger.warning(
                "DIFC: __NEXT_DATA__ available but no company list found. "
                "pageProps: %s",
                json.dumps(
                    (self._next_data.get("props") or {}).get("pageProps") or {}, default=str
                )[:500]
            )

        # ── Strategy 2: Next.js /_next/data/ JSON route ───────────────────
        items, err = self._fetch_next_json_page(page_number, page_size)
        if items is not None and not err:
            self._strategy = ("next_json", None)
            _logger.info("DIFC: using Next.js JSON data route strategy")
            return items, len(items), ""
        if err:
            errors.append(f"Next.js data route: {err}")

        # ── Strategy 3: discovered API base + /companies or /public-register
        if self._api_base:
            for path in ("/companies", "/public-register", "/register",
                         "/api/companies", "/api/register"):
                url = self._api_base + path
                params = {"companyName": "", "pageNumber": page_number,
                          "pageSize": page_size, "page": page_number}
                ok, data, status, err_s, snippet = self._api_get(url, params)
                label = f"API base GET {path}"
                if ok:
                    items = self._extract_items(data) or self._find_company_list(data, 0, 4)
                    if items:
                        self._strategy = ("api_base_get", url)
                        return items, self._extract_total(data, len(items)), ""
                    errors.append(f"{label} → 200 but no items | keys={list(data.keys()) if isinstance(data, dict) else ''}")
                else:
                    errors.append(f"{label} → {err_s} | {snippet[:100]}")

        # ── Strategy 4: POST /api/handleRequest with CSRF token ───────────
        post_url = self._origin + "/api/handleRequest"
        for action in _POST_ACTIONS:
            body = {"action": action, "companyName": "",
                    "pageNumber": page_number, "pageSize": page_size}
            ok, data, status, err_s, snippet = self._api_post(post_url, body)
            label = f"POST /api/handleRequest action={action}"
            if ok:
                items = self._extract_items(data) or self._find_company_list(data, 0, 4)
                if items:
                    self._strategy = ("post_action", action)
                    return items, self._extract_total(data, len(items)), ""
                errors.append(f"{label} → 200 but no items | keys={list(data.keys()) if isinstance(data, dict) else ''} | {snippet[:100]}")
            else:
                errors.append(f"{label} → {err_s} | {snippet[:100]}")
                _logger.warning("DIFC %s → %s | %s", label, err_s, snippet[:100])

        # ── Strategy 5: HTML scrape (server-rendered table fallback) ──────
        if page_number == 1 and self._page_html and BS4_AVAILABLE:
            items = self._scrape_html_table(self._page_html)
            if items:
                self._strategy = ("html_table", None)
                _logger.info("DIFC: using HTML table scrape strategy")
                return items, len(items), ""
            errors.append("HTML scrape: no company table found in page")

        summary = "\n".join(errors)
        return [], 0, f"All strategies failed:\n{summary}"

    def _fetch_with_strategy(self, strategy, page_number, page_size):
        kind, key = strategy
        if kind == "next_json":
            items, err = self._fetch_next_json_page(page_number, page_size)
            return (items or [], len(items or []), err)
        if kind == "api_base_get" and key:
            params = {"companyName": "", "pageNumber": page_number,
                      "pageSize": page_size, "page": page_number}
            ok, data, status, err, snippet = self._api_get(key, params)
            if ok:
                items = self._extract_items(data) or self._find_company_list(data, 0, 4) or []
                return items, self._extract_total(data, len(items)), ""
            return [], 0, f"{err} | {snippet[:100]}"
        if kind == "post_action" and key:
            post_url = self._origin + "/api/handleRequest"
            body = {"action": key, "companyName": "",
                    "pageNumber": page_number, "pageSize": page_size}
            ok, data, status, err, snippet = self._api_post(post_url, body)
            if ok:
                items = self._extract_items(data) or self._find_company_list(data, 0, 4) or []
                return items, self._extract_total(data, len(items)), ""
            return [], 0, f"{err} | {snippet[:100]}"
        # next_data and html_table only work for page 1
        return [], 0, f"Strategy {kind} does not support page {page_number}"

    # ── HTML table scrape ─────────────────────────────────────────────────────

    def _scrape_html_table(self, html):
        """Last-resort: parse a server-rendered HTML table of companies."""
        if not BS4_AVAILABLE:
            return []
        soup = BeautifulSoup(html, "html.parser")
        items = []
        # Look for table rows
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower()
                       for th in table.find_all("th")]
            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if not cells:
                    continue
                item = {}
                if headers:
                    for h, val in zip(headers, cells):
                        item[h] = val
                else:
                    if cells:
                        item["name"] = cells[0]
                    if len(cells) > 1:
                        item["type"] = cells[1]
                    if len(cells) > 2:
                        item["status"] = cells[2]
                if item:
                    items.append(item)
        return items

    # ── Envelope unwrapping ───────────────────────────────────────────────────

    @staticmethod
    def _extract_items(data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return None
        for extractor in _ARRAY_PATHS:
            try:
                result = extractor(data)
                if isinstance(result, list):
                    return result
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_total(data, fallback=0):
        if not isinstance(data, dict):
            return fallback
        for key in _TOTAL_KEYS:
            val = data.get(key)
            if val is None and isinstance(data.get("data"), dict):
                val = data["data"].get(key)
            if isinstance(val, int) and val >= 0:
                return val
        return fallback

    # ── ParsedLead construction ───────────────────────────────────────────────

    def item_to_lead(self, item, source_url):
        if not isinstance(item, dict):
            return None
        lead = ParsedLead()
        lead.source_url = source_url
        lead.country_name = "United Arab Emirates"
        lead.company_name = self._first(item, _NAME_KEYS)
        lead.website      = self._first(item, _WEB_KEYS)
        lead.email        = self._first(item, _EMAIL_KEYS)
        lead.phone        = self._first(item, _PHONE_KEYS)
        addr = self._first(item, _ADDR_KEYS)
        lead.city = addr[:200] if addr else "Dubai"
        license_type = self._first(item, _TYPE_KEYS)
        status       = self._first(item, _STATUS_KEYS)
        parts = [p for p in [license_type, status] if p]
        lead.industry = " — ".join(parts)[:200] if parts else ""
        desc_lines = ["DIFC Public Register"]
        for key in ("licenseNumber", "license_number", "LicenseNumber",
                    "registrationNumber", "regNumber"):
            val = item.get(key)
            if val:
                desc_lines.append(f"License/Reg No: {val}")
                break
        if license_type:
            desc_lines.append(f"Type: {license_type}")
        if status:
            desc_lines.append(f"Status: {status}")
        lead.description = "\n".join(desc_lines)
        lead.raw_payload = {"source": "DIFC Public Register", **item}
        if not (lead.company_name or lead.email or lead.phone):
            return None
        return lead

    @staticmethod
    def _first(d, keys):
        for k in keys:
            v = d.get(k)
            if v and isinstance(v, str):
                val = v.strip()
                if val:
                    return val
        return ""
