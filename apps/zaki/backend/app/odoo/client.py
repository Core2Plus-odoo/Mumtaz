"""Standard Odoo JSON-RPC client — no custom Mumtaz modules required."""
import httpx
import itertools

_req_id = itertools.count(1)


async def _rpc(base_url: str, endpoint: str, params: dict, session_id: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["Cookie"] = f"session_id={session_id}"

    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": next(_req_id),
        "params": params,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{base_url.rstrip('/')}{endpoint}", json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise ConnectionError(f"Cannot reach Odoo at {base_url}: {exc}") from exc

    body = resp.json()

    if body.get("error"):
        msg = body["error"].get("data", {}).get("message") or str(body["error"])
        if "session" in msg.lower() or "login" in msg.lower() or resp.status_code == 401:
            err = Exception("Odoo session expired. Please reconnect.")
            err.code = "SESSION_EXPIRED"  # type: ignore[attr-defined]
            raise err
        raise Exception(f"Odoo error: {msg}")

    # Extract new session_id if set
    new_session = None
    set_cookie = resp.headers.get("set-cookie", "")
    if "session_id=" in set_cookie:
        import re
        m = re.search(r"session_id=([^;]+)", set_cookie)
        if m:
            new_session = m.group(1)

    return {"result": body.get("result"), "new_session": new_session}


async def authenticate(base_url: str, db: str, email: str, password: str) -> dict:
    """Returns {uid, name, session_id}."""
    data = await _rpc(base_url, "/web/session/authenticate", {
        "db": db, "login": email, "password": password,
    })
    result = data["result"]
    if not result or not result.get("uid"):
        raise Exception("Invalid email or password.")
    return {
        "uid":       result["uid"],
        "name":      result.get("name", email),
        "session_id": data["new_session"] or result.get("session_id"),
    }


async def search_read(conn: dict, model: str, domain: list, fields: list, **kwargs) -> list:
    data = await _rpc(conn["base_url"], "/web/dataset/call_kw", {
        "model":  model,
        "method": "search_read",
        "args":   [domain],
        "kwargs": {
            "fields": fields,
            "limit":  kwargs.get("limit", 500),
            "offset": kwargs.get("offset", 0),
            "order":  kwargs.get("order", ""),
        },
    }, conn["session_id"])
    return data["result"] or []
