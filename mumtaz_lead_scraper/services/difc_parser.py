"""
DIFC Public Register — Dedicated Scraper
=========================================
The DIFC Public Register (https://www.difc.com/business/public-register) is a
Next.js SPA backed by Sitecore XM Cloud.  Static HTML contains no company data.

Two API strategies are tried in order:

  Strategy A — GET /api/actions/difc/request-company-details
    POST to this path returned 405 (Method Not Allowed) in probe tests,
    meaning the route exists but only accepts GET.
    Query params: companyName, pageNumber, pageSize

  Strategy B — POST /api/handleRequest
    Tries multiple action name candidates since HTTP 500 means the route
    exists but the action name is unrecognised.
    Body: {"action": "<candidate>", "companyName": "", "pageNumber": 1, ...}

Usage in Odoo:
  - Source Type  : DIFC Public Register
  - URL          : https://www.difc.com/business/public-register
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

_DEFAULT_PAGE_SIZE = 20

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.difc.com",
    "Referer": "https://www.difc.com/business/public-register",
}

# Strategy A: GET endpoint (POST to this path returned 405 in earlier probe)
_GET_ENDPOINTS = [
    "/api/actions/difc/request-company-details",
    "/api/actions/request-company-details",
    "/api/actions/difc/public-register",
]

# Strategy B: POST /api/handleRequest with different action name candidates
_HANDLE_REQUEST_PATH = "/api/handleRequest"
_ACTION_CANDIDATES = [
    "request-company-details",
    "difc/request-company-details",
    "difc/publicRegister",
    "publicRegister",
    "getPublicRegister",
    "difc/getCompanies",
    "getCompanies",
    "difc/companies",
]

# Response envelope unwrappers — tried in order to locate the item array
_ARRAY_PATHS = [
    lambda d: d.get("data", {}).get("results") if isinstance(d.get("data"), dict) else None,
    lambda d: d.get("data") if isinstance(d.get("data"), list) else None,
    lambda d: d.get("results") if isinstance(d.get("results"), list) else None,
    lambda d: d.get("Items") if isinstance(d.get("Items"), list) else None,
    lambda d: d.get("items") if isinstance(d.get("items"), list) else None,
    lambda d: d.get("companies") if isinstance(d.get("companies"), list) else None,
    lambda d: d.get("entities") if isinstance(d.get("entities"), list) else None,
    lambda d: d.get("records") if isinstance(d.get("records"), list) else None,
    lambda d: (d.get("data", {}).get("search", {}) or {}).get("results"),
]

_TOTAL_KEYS = ("totalCount", "total_count", "TotalCount", "Total",
               "total", "count", "Count", "totalResults")

# Field-name candidates for ParsedLead mapping
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


# ── Main parser class ─────────────────────────────────────────────────────────

class DIFCRegisterParser:
    """
    Fetches and parses DIFC Public Register data.
    Auto-detects the working API strategy on the first call.
    """

    def __init__(self, base_url, delay=2.0, timeout=20):
        parsed = urlparse(base_url)
        self._origin = f"{parsed.scheme}://{parsed.netloc}"
        self._delay = max(delay, 1.0)
        self._timeout = timeout
        self._session = None
        self._last_req = 0.0
        # Locked-in strategy once discovered: ("GET", url) or ("POST", action)
        self._strategy = None

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
        """Visit the public register page to collect session cookies."""
        if getattr(self, "_session_warmed", False):
            return
        try:
            sess = self._get_session()
            resp = sess.get(
                f"{self._origin}/business/public-register", timeout=self._timeout
            )
            self._last_req = time.time()
            _logger.info("DIFC warm-up: GET /business/public-register → %s", resp.status_code)
        except Exception as exc:
            _logger.warning("DIFC warm-up failed: %s", exc)
        self._session_warmed = True

    def _do_get(self, path, page_number, page_size, company_name=""):
        self._rate_limit()
        sess = self._get_session()
        url = self._origin + path
        params = {
            "companyName": company_name,
            "pageNumber": page_number,
            "pageSize": page_size,
            "page": page_number,
            "size": page_size,
        }
        try:
            resp = sess.get(url, params=params, timeout=self._timeout)
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

    def _do_post(self, action, page_number, page_size, company_name=""):
        self._rate_limit()
        sess = self._get_session()
        url = self._origin + _HANDLE_REQUEST_PATH
        body = {
            "action": action,
            "companyName": company_name,
            "pageNumber": page_number,
            "pageSize": page_size,
        }
        try:
            resp = sess.post(url, json=body, timeout=self._timeout)
            self._last_req = time.time()
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", "5"))
                time.sleep(wait)
                resp = sess.post(url, json=body, timeout=self._timeout)
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

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_page(self, page_number, page_size=_DEFAULT_PAGE_SIZE):
        """
        Fetch one page.  Returns (items, total, error_str).
        On first call probes all strategies; subsequent calls reuse winner.
        """
        if page_number == 1:
            self._warm_session()

        # Reuse confirmed strategy
        if self._strategy is not None:
            kind, key = self._strategy
            if kind == "GET":
                ok, data, status, err, snippet = self._do_get(key, page_number, page_size)
            else:
                ok, data, status, err, snippet = self._do_post(key, page_number, page_size)
            if ok:
                items = self._extract_items(data)
                if items is not None:
                    return items, self._extract_total(data, len(items)), ""
            return [], 0, f"Strategy {kind}:{key} failed — {err} | {snippet[:150]}"

        # Discovery phase — try all strategies
        variant_errors = []

        # Strategy A: GET endpoints
        for path in _GET_ENDPOINTS:
            ok, data, status, err, snippet = self._do_get(path, page_number, page_size)
            label = f"GET {path}"
            if not ok:
                variant_errors.append(f"{label} → {err} | {snippet[:120]}")
                _logger.warning("DIFC probe: %s → %s | %s", label, err, snippet[:120])
                continue
            items = self._extract_items(data)
            if items is None:
                detail = (
                    f"{label} → HTTP {status} OK but no item array; "
                    f"keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__} "
                    f"| {snippet[:120]}"
                )
                variant_errors.append(detail)
                _logger.warning("DIFC probe: %s", detail)
                continue
            self._strategy = ("GET", path)
            _logger.info("DIFC: using strategy GET %s", path)
            return items, self._extract_total(data, len(items)), ""

        # Strategy B: POST /api/handleRequest with action name candidates
        for action in _ACTION_CANDIDATES:
            ok, data, status, err, snippet = self._do_post(action, page_number, page_size)
            label = f"POST handleRequest action={action}"
            if not ok:
                variant_errors.append(f"{label} → {err} | {snippet[:120]}")
                _logger.warning("DIFC probe: %s → %s | %s", label, err, snippet[:120])
                continue
            items = self._extract_items(data)
            if items is None:
                detail = (
                    f"{label} → HTTP {status} OK but no item array; "
                    f"keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__} "
                    f"| {snippet[:120]}"
                )
                variant_errors.append(detail)
                _logger.warning("DIFC probe: %s", detail)
                continue
            self._strategy = ("POST", action)
            _logger.info("DIFC: using strategy POST action=%s", action)
            return items, self._extract_total(data, len(items)), ""

        return [], 0, "All strategies failed:\n" + "\n".join(variant_errors)

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
