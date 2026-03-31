"""
DIFC Public Register — Dedicated Scraper
=========================================
The DIFC Public Register (https://www.difc.com/business/public-register) is a
Next.js SPA backed by Sitecore XM Cloud.  Static HTML contains no company data.
The page hydrates via a server-side Next.js API route:

  POST https://www.difc.com/api/handleRequest
  Content-Type: application/json
  Body: {"action": "difc/request-company-details",
         "companyName": "", "pageNumber": 1, "pageSize": 20}

The endpoint returns a JSON document.  Multiple response envelope shapes are
handled gracefully so that schema changes do not break the scraper silently.

Usage in Odoo:
  - Source Type  : DIFC Public Register
  - URL          : https://www.difc.com/business/public-register
    (the scheme + host is extracted; only https://www.difc.com is contacted)
  - Max Pages    : controls how many API pages to fetch (default 20)
  - request_delay: seconds between API calls (default 2.0)
"""

import json
import logging
import time
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .parser import ParsedLead

# ── Constants ─────────────────────────────────────────────────────────────────

_ACTION = "difc/request-company-details"
_API_PATH = "/api/handleRequest"
_DEFAULT_PAGE_SIZE = 20

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://www.difc.com",
    "Referer": "https://www.difc.com/business/public-register",
    "X-Requested-With": "XMLHttpRequest",
}

# Candidate field names in the response — handled in priority order
_NAME_KEYS   = ("companyName", "company_name", "name", "Name", "entityName",
                "legalName", "LegalName", "title")
_TYPE_KEYS   = ("licenseType", "license_type", "type", "Type", "entityType",
                "category", "Category", "companyType")
_STATUS_KEYS = ("status", "Status", "licenseStatus", "entityStatus", "state")
_WEB_KEYS    = ("website", "Website", "url", "webAddress", "web")
_EMAIL_KEYS  = ("email", "Email", "emailAddress", "contactEmail")
_PHONE_KEYS  = ("phone", "Phone", "phoneNumber", "contactPhone", "telephone")
_ADDR_KEYS   = ("address", "Address", "registeredAddress", "officeAddress",
                "location", "Location")
_COUNTRY_KEYS = ("country", "Country", "countryName", "nationality")

# Envelope shapes tried to locate the item array
_ARRAY_PATHS = [
    lambda d: d.get("data", {}).get("results") if isinstance(d.get("data"), dict) else None,
    lambda d: d.get("data") if isinstance(d.get("data"), list) else None,
    lambda d: d.get("results") if isinstance(d.get("results"), list) else None,
    lambda d: d.get("Items") if isinstance(d.get("Items"), list) else None,
    lambda d: d.get("items") if isinstance(d.get("items"), list) else None,
    lambda d: d.get("companies") if isinstance(d.get("companies"), list) else None,
    lambda d: d.get("entities") if isinstance(d.get("entities"), list) else None,
    lambda d: d.get("records") if isinstance(d.get("records"), list) else None,
    # Sitecore Edge GraphQL envelope
    lambda d: (d.get("data", {}).get("search", {}) or {}).get("results"),
]

# Total-count field names (for logging)
_TOTAL_KEYS = ("totalCount", "total_count", "TotalCount", "Total",
               "total", "count", "Count", "totalResults")

# ── Request builder helpers ───────────────────────────────────────────────────

def _build_request_bodies(page_number, page_size, company_name=""):
    """
    Return a list of candidate JSON bodies to try.
    Different Sitecore action handler versions use different field names.
    """
    base = {"action": _ACTION, "companyName": company_name}
    variants = [
        {**base, "pageNumber": page_number, "pageSize": page_size},
        {**base, "page": page_number, "pageSize": page_size},
        {**base, "pageNumber": page_number, "PageSize": page_size},
        {**base, "page_number": page_number, "page_size": page_size},
        {**base, "offset": (page_number - 1) * page_size, "limit": page_size},
    ]
    return variants


# ── Main parser class ─────────────────────────────────────────────────────────

class DIFCRegisterParser:
    """
    Fetches and parses DIFC Public Register data via the /api/handleRequest
    Next.js API route.  Each call retrieves one page of results.
    """

    def __init__(self, base_url, delay=2.0, timeout=20):
        parsed = urlparse(base_url)
        self._origin = f"{parsed.scheme}://{parsed.netloc}"
        self._api_url = self._origin + _API_PATH
        self._delay = max(delay, 1.0)
        self._timeout = timeout
        self._session = None
        self._last_req = 0.0
        # remember which request body variant actually worked
        self._working_body_variant = None

    def _get_session(self):
        if self._session is None:
            if not REQUESTS_AVAILABLE:
                raise RuntimeError("requests library is not installed")
            self._session = requests.Session()
            self._session.headers.update(_BROWSER_HEADERS)
            self._session.headers["Referer"] = f"{self._origin}/business/public-register"
            self._session.headers["Origin"] = self._origin
        return self._session

    def _rate_limit(self):
        elapsed = time.time() - self._last_req
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)

    def _warm_session(self):
        """
        Visit the public register page first to pick up any session cookies or
        CSRF tokens the Next.js app sets before allowing API calls.
        """
        if getattr(self, "_session_warmed", False):
            return
        try:
            sess = self._get_session()
            warmup_url = f"{self._origin}/business/public-register"
            resp = sess.get(warmup_url, timeout=self._timeout)
            self._last_req = time.time()
            _logger.info("DIFC session warm-up: GET %s → %s", warmup_url, resp.status_code)
        except Exception as exc:
            _logger.warning("DIFC session warm-up failed: %s", exc)
        self._session_warmed = True

    def _request(self, method, body):
        """
        Execute one HTTP request (POST or GET).
        Returns (ok, data_or_None, status_code, err_str, body_snippet).
        """
        self._rate_limit()
        sess = self._get_session()
        try:
            if method == "GET":
                params = {k: str(v) for k, v in body.items()}
                resp = sess.get(self._api_url, params=params, timeout=self._timeout)
            else:
                resp = sess.post(self._api_url, json=body, timeout=self._timeout)
            self._last_req = time.time()

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", "5"))
                _logger.warning("DIFC API rate-limited — sleeping %ds", wait)
                time.sleep(wait)
                if method == "GET":
                    resp = sess.get(self._api_url, params=params, timeout=self._timeout)
                else:
                    resp = sess.post(self._api_url, json=body, timeout=self._timeout)
                self._last_req = time.time()

            snippet = resp.text[:300].replace("\n", " ")
            if resp.status_code not in (200, 201):
                return False, None, resp.status_code, f"HTTP {resp.status_code}", snippet

            try:
                return True, resp.json(), resp.status_code, "", snippet
            except ValueError:
                return False, None, resp.status_code, "Response is not valid JSON", snippet

        except requests.exceptions.Timeout:
            return False, None, 0, "Request timed out", ""
        except requests.exceptions.ConnectionError as exc:
            return False, None, 0, f"Connection error: {exc}", ""
        except Exception as exc:
            return False, None, 0, str(exc), ""

    def fetch_page(self, page_number, page_size=_DEFAULT_PAGE_SIZE):
        """
        Fetch one page of DIFC register data.
        Returns (items: list[dict], total: int, error: str).
        The error string includes per-variant diagnostics when all fail.
        """
        if page_number == 1:
            self._warm_session()

        post_bodies = _build_request_bodies(page_number, page_size)
        # Also try GET versions of the first two POST variants
        candidates = (
            [("POST", post_bodies[self._working_body_variant])]
            if self._working_body_variant is not None
            else (
                [("POST", b) for b in post_bodies]
                + [("GET", post_bodies[0]), ("GET", post_bodies[1])]
            )
        )

        variant_errors = []
        for idx, (method, body) in enumerate(candidates):
            ok, data, status, err, snippet = self._request(method, body)
            if not ok:
                detail = f"variant {idx} ({method}) → {err} | response: {snippet[:150]}"
                variant_errors.append(detail)
                _logger.warning("DIFC %s", detail)
                continue

            items = self._extract_items(data)
            if items is None:
                detail = (
                    f"variant {idx} ({method}) → HTTP {status} OK but no item array; "
                    f"keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__} "
                    f"| snippet: {snippet[:150]}"
                )
                variant_errors.append(detail)
                _logger.warning("DIFC %s", detail)
                continue

            if self._working_body_variant is None:
                self._working_body_variant = idx
                _logger.info(
                    "DIFC: working variant is #%d (%s): %s", idx, method, json.dumps(body)
                )

            total = self._extract_total(data, len(items))
            return items, total, ""

        summary = " || ".join(variant_errors)
        return [], 0, f"All variants failed: {summary}"

    # ── Envelope unwrapping ───────────────────────────────────────────────

    @staticmethod
    def _extract_items(data):
        """Walk candidate paths to find a list of company records."""
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

    # ── ParsedLead construction ───────────────────────────────────────────

    def item_to_lead(self, item, source_url):
        """Convert a single API record dict into a ParsedLead."""
        if not isinstance(item, dict):
            return None

        lead = ParsedLead()
        lead.source_url = source_url
        lead.country_name = "United Arab Emirates"

        lead.company_name = self._first(item, _NAME_KEYS)
        lead.website     = self._first(item, _WEB_KEYS)
        lead.email       = self._first(item, _EMAIL_KEYS)
        lead.phone       = self._first(item, _PHONE_KEYS)

        # Build city / address
        addr = self._first(item, _ADDR_KEYS)
        if addr:
            lead.city = addr[:200]
        else:
            lead.city = "Dubai"  # DIFC is in Dubai

        # Industry / entity type from license type field
        license_type = self._first(item, _TYPE_KEYS)
        status       = self._first(item, _STATUS_KEYS)
        parts = [p for p in [license_type, status] if p]
        lead.industry = " — ".join(parts)[:200] if parts else ""

        # Description with all available structured data
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
        """Return the first non-empty string value from d matching any key in keys."""
        for k in keys:
            v = d.get(k)
            if v and isinstance(v, str):
                val = v.strip()
                if val:
                    return val
        return ""
