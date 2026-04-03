"""
HTTP Fetcher
============
Responsible for fetching HTML/JSON from URLs with rate limiting,
retry logic, and optional robots.txt awareness.
"""

import logging
import time
import urllib.robotparser
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MumtazLeadScraper/1.0; +https://mumtaz.digital)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    _logger.warning(
        "requests library not available — install it: pip install requests beautifulsoup4"
    )


class FetchResult:
    def __init__(self, success, content="", status_code=0, error="", final_url=""):
        self.success = success
        self.content = content
        self.status_code = status_code
        self.error = error
        self.final_url = final_url

    def __repr__(self):
        return f"<FetchResult success={self.success} status={self.status_code}>"


class PageFetcher:
    """
    Fetches web pages with rate limiting, retries, and robots.txt support.
    """

    def __init__(self, delay=2.0, timeout=DEFAULT_TIMEOUT, max_retries=MAX_RETRIES):
        self.delay = max(delay, 1.0)  # enforce minimum 1s delay
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request_time = 0.0
        self._robots_cache = {}

    def fetch(self, url, headers=None) -> FetchResult:
        if not REQUESTS_AVAILABLE:
            return FetchResult(False, error="requests library not installed")

        merged = {**DEFAULT_HEADERS, **(headers or {})}
        self._rate_limit()

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.get(
                    url, headers=merged, timeout=self.timeout, allow_redirects=True
                )
                self._last_request_time = time.time()

                if resp.status_code == 200:
                    return FetchResult(
                        True,
                        content=resp.text,
                        status_code=200,
                        final_url=resp.url,
                    )
                if resp.status_code in (429, 503):
                    wait = 2 ** attempt
                    _logger.warning("Rate limited (%s) — waiting %ss", url, wait)
                    time.sleep(wait)
                    continue
                return FetchResult(
                    False,
                    status_code=resp.status_code,
                    error=f"HTTP {resp.status_code}",
                )
            except requests.exceptions.Timeout:
                _logger.warning("Timeout %s (attempt %d/%d)", url, attempt, self.max_retries)
                if attempt == self.max_retries:
                    return FetchResult(False, error="Request timed out after retries")
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as exc:
                return FetchResult(False, error=f"Connection error: {exc}")
            except Exception as exc:
                _logger.exception("Unexpected fetch error: %s", url)
                return FetchResult(False, error=str(exc))

        return FetchResult(False, error="Max retries exceeded")

    def is_allowed_by_robots(self, url) -> bool:
        """Return True if the URL is allowed by robots.txt (or robots.txt unreachable)."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        if robots_url not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self._robots_cache[robots_url] = rp
            except Exception:
                self._robots_cache[robots_url] = None  # assume allowed

        rp = self._robots_cache.get(robots_url)
        if rp is None:
            return True
        return rp.can_fetch(DEFAULT_HEADERS["User-Agent"], url)

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
