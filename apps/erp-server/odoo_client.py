"""
Odoo JSON-RPC client — per-tenant session pool.

Each tenant has their own Odoo database. We authenticate with a service-account
(admin credentials stored on the companies row) and cache the session cookie.
On session expiry Odoo returns error code 100; we re-authenticate transparently.

Usage:
    from odoo_client import get_session, OdooError

    sess = get_session(url, db, login, password)
    partners = sess.search_read("res.partner", [["is_company", "=", True]],
                                fields=["id", "name", "email"])
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import urllib.error
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OdooError(Exception):
    """Raised when Odoo returns a JSON-RPC error block."""

    def __init__(self, error: dict):
        self.code: int = error.get("code", 0)
        self.message: str = error.get("message", "Unknown Odoo error")
        self.data: dict = error.get("data", {})
        super().__init__(self.message)

    def is_auth_error(self) -> bool:
        return (
            self.code == 100
            or "session" in str(self.data).lower()
            or "access" in str(self.data).lower()
        )

    def is_not_found(self) -> bool:
        return self.code == 404 or "not found" in self.message.lower()


class OdooConnectionError(Exception):
    """Raised when we cannot reach the Odoo server at all."""


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class OdooSession:
    """
    One authenticated connection to a specific (odoo_url, database, login).

    Thread-safe: a lock guards re-authentication so parallel requests don't
    all try to log in simultaneously after a session expires.
    """

    def __init__(self, url: str, db: str, login: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.login = login
        self._password = password
        self.session_id: Optional[str] = None
        self.uid: Optional[int] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    def _http_post(self, path: str, payload: dict) -> tuple[dict, str]:
        """
        POST JSON payload to path, return (parsed_body, raw_set_cookie).
        Raises OdooConnectionError on network failures.
        """
        raw = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.url + path,
            data=raw,
            headers={"Content-Type": "application/json"},
        )
        if self.session_id:
            req.add_header("Cookie", f"session_id={self.session_id}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                set_cookie = resp.headers.get("Set-Cookie", "")
                body = json.loads(resp.read())
                return body, set_cookie
        except urllib.error.HTTPError as exc:
            raise OdooConnectionError(f"HTTP {exc.code} from Odoo: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise OdooConnectionError(f"Cannot reach Odoo at {self.url}: {exc.reason}") from exc

    def _extract_session_cookie(self, set_cookie: str) -> Optional[str]:
        for part in set_cookie.split(";"):
            part = part.strip()
            if part.lower().startswith("session_id="):
                return part.split("=", 1)[1]
        return None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> int:
        """Authenticate and store session_id. Returns uid."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {
                "db": self.db,
                "login": self.login,
                "password": self._password,
            },
        }
        body, set_cookie = self._http_post("/web/session/authenticate", payload)

        if "error" in body:
            raise OdooError(body["error"])

        result = body.get("result", {})
        uid = result.get("uid")
        if not uid:
            raise OdooError({"code": 401, "message": f"Auth failed for db={self.db} login={self.login}", "data": {}})

        self.uid = uid
        sid = self._extract_session_cookie(set_cookie)
        if sid:
            self.session_id = sid
        elif result.get("session_id"):
            self.session_id = result["session_id"]

        return uid

    # ------------------------------------------------------------------
    # JSON-RPC call_kw
    # ------------------------------------------------------------------

    def _call_kw_raw(self, model: str, method: str, args: list, kwargs: dict) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": int(time.time() * 1000),
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs,
            },
        }
        body, set_cookie = self._http_post("/web/dataset/call_kw", payload)

        # Refresh session cookie if Odoo rotated it
        sid = self._extract_session_cookie(set_cookie)
        if sid:
            self.session_id = sid

        if "error" in body:
            raise OdooError(body["error"])

        return body.get("result")

    def call_kw(self, model: str, method: str, args: list | None = None, kwargs: dict | None = None) -> Any:
        """Call any Odoo model method. Re-authenticates once on session expiry."""
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        with self._lock:
            if not self.session_id:
                self.authenticate()

        try:
            return self._call_kw_raw(model, method, args, kwargs)
        except OdooError as exc:
            if exc.is_auth_error():
                with self._lock:
                    self.session_id = None
                    self.authenticate()
                return self._call_kw_raw(model, method, args, kwargs)
            raise

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        kwargs: dict = {"fields": fields or [], "limit": limit, "offset": offset}
        if order:
            kwargs["order"] = order
        return self.call_kw(model, "search_read", [domain or []], kwargs) or []

    def search_count(self, model: str, domain: list | None = None) -> int:
        return self.call_kw(model, "search_count", [domain or []]) or 0

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        return self.call_kw(model, "read", [ids], {"fields": fields or []}) or []

    def create(self, model: str, vals: dict) -> int:
        return self.call_kw(model, "create", [vals])

    def write(self, model: str, ids: list[int], vals: dict) -> bool:
        return self.call_kw(model, "write", [ids, vals])

    def unlink(self, model: str, ids: list[int]) -> bool:
        return self.call_kw(model, "unlink", [ids])

    def name_search(self, model: str, name: str = "", domain: list | None = None, limit: int = 20) -> list:
        return self.call_kw(
            model, "name_search", [],
            {"name": name, "args": domain or [], "limit": limit},
        ) or []

    def fields_get(self, model: str, attributes: list[str] | None = None) -> dict:
        kwargs = {}
        if attributes:
            kwargs["attributes"] = attributes
        return self.call_kw(model, "fields_get", [], kwargs) or {}

    def action_confirm(self, model: str, ids: list[int]) -> Any:
        return self.call_kw(model, "action_confirm", [ids])

    def action_post(self, model: str, ids: list[int]) -> Any:
        return self.call_kw(model, "action_post", [ids])

    def test_connection(self) -> dict:
        """Authenticate and return server info. Use to validate credentials."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {},
        }
        body, _ = self._http_post("/web/webclient/version_info", payload)
        if "error" in body:
            raise OdooError(body["error"])
        version = body.get("result", {})

        uid = self.authenticate()
        return {
            "ok": True,
            "uid": uid,
            "db": self.db,
            "server_version": version.get("server_version", "unknown"),
            "server_serie": version.get("server_serie", "unknown"),
        }


# ---------------------------------------------------------------------------
# Session pool  {(url, db, login) → OdooSession}
# ---------------------------------------------------------------------------

_pool: dict[tuple, OdooSession] = {}
_pool_lock = threading.Lock()


def get_session(url: str, db: str, login: str, password: str) -> OdooSession:
    """Return a cached OdooSession, creating it if needed."""
    key = (url.rstrip("/"), db, login)
    with _pool_lock:
        if key not in _pool:
            _pool[key] = OdooSession(url, db, login, password)
        return _pool[key]


def invalidate_session(url: str, db: str, login: str) -> None:
    """Remove a session from the pool (e.g., after credential change)."""
    key = (url.rstrip("/"), db, login)
    with _pool_lock:
        _pool.pop(key, None)
