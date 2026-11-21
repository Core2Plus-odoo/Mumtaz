"""Open the provisioned workspace the way its first user would.

    open_workspace.py BASE_URL SUMMARY_JSON

Follows the administrator's one-time link over HTTP, sets a password, lands
in the Odoo web client, and checks the session is in the tenant's own
database with the ERP apps installed. Then checks the link no longer works.
"""
import json
import re
import secrets
import sys
from urllib.parse import urlsplit

import requests

BASE = sys.argv[1].rstrip("/")
with open(sys.argv[2]) as handle:
    SUMMARY = json.load(handle)
DB, LOGIN = SUMMARY["database"], SUMMARY["login"]


def check(condition, message):
    if not condition:
        print("WORKSPACE FAILED: %s" % message)
        sys.exit(1)
    print("  ok  %s" % message)


def rpc(session, path, params):
    reply = session.post(BASE + path, json={"jsonrpc": "2.0", "method": "call", "params": params},
                         timeout=120).json()
    if "error" in reply:
        raise RuntimeError(reply["error"].get("data", {}).get("message") or reply["error"])
    return reply["result"]


link = urlsplit(SUMMARY["access_link"])
check(link.path == "/web/signup" and "token=" in link.query, "link is Odoo's own invitation URL")
local_link = "%s%s?%s" % (BASE, link.path, link.query)

# -- the administrator opens the link and chooses a password ------------------
admin = requests.Session()
page = admin.get(local_link, timeout=120)
check(page.status_code == 200, "set-password page opens")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text)
token = re.search(r'name="token"\s+value="([^"]+)"', page.text)
check(bool(csrf and token), "page carries the form and its token")
check(LOGIN in page.text, "page is for the tenant administrator's login")

password = secrets.token_urlsafe(18)
done = admin.post(BASE + "/web/signup", timeout=120, data={
    "csrf_token": csrf.group(1), "token": token.group(1), "db": DB,
    "login": LOGIN, "name": "Journey Owner",
    "password": password, "confirm_password": password,
})
check(done.status_code == 200, "password accepted")

info = rpc(admin, "/web/session/get_session_info", {})
check(info.get("uid") == 2, "signed in as the tenant administrator (uid 2)")
check(info.get("db") == DB, "session is in the tenant's own database: %s" % DB)
check(info.get("username") == LOGIN, "session login is %s" % LOGIN)

client = admin.get(BASE + "/odoo", timeout=120)
check(client.status_code == 200 and "web.assets_web" in client.text, "ERP web client loads at /odoo")

installed = rpc(admin, "/web/dataset/call_kw/ir.module.module/search_read", {
    "model": "ir.module.module", "method": "search_read",
    "args": [[("name", "in", SUMMARY["modules"]), ("state", "=", "installed")], ["name"]],
    "kwargs": {},
})
names = sorted(row["name"] for row in installed)
check(names == sorted(SUMMARY["modules"]), "every module of the profile is installed: %s" % ", ".join(names))
company = rpc(admin, "/web/dataset/call_kw/res.company/search_read", {
    "model": "res.company", "method": "search_read", "args": [[], ["name"]], "kwargs": {},
})
check(len(company) == 1, "one company in the workspace: %s" % company[0]["name"])

# -- the password works on its own, the link does not work twice --------------
again = requests.Session()
auth = rpc(again, "/web/session/authenticate", {"db": DB, "login": LOGIN, "password": password})
check(auth.get("uid") == 2, "the chosen password signs in")

stranger = requests.Session()
replay = stranger.get(local_link, timeout=120)
check("Invalid signup token" in replay.text,
      "the one-time link is dead after first sign-in")
dead = stranger.post(BASE + "/web/signup", timeout=120, data={
    "csrf_token": (re.search(r'name="csrf_token"\s+value="([^"]+)"', replay.text) or [None, ""])[1],
    "token": token.group(1), "db": DB, "login": LOGIN, "name": "Stranger",
    "password": "stranger-password-1", "confirm_password": "stranger-password-1",
})
try:
    # Odoo answers "Session expired" to a visitor who is not signed in.
    signed_in = bool(rpc(stranger, "/web/session/get_session_info", {}).get("uid"))
except RuntimeError:
    signed_in = False
check(not signed_in, "replaying the link does not sign anyone in (HTTP %s)" % dead.status_code)
check(rpc(requests.Session(), "/web/session/authenticate",
          {"db": DB, "login": LOGIN, "password": password}).get("uid") == 2,
      "the administrator's password is unchanged by the replay")
try:
    rpc(requests.Session(), "/web/session/authenticate",
        {"db": DB, "login": LOGIN, "password": "not-the-password"})
    check(False, "a wrong password is refused")
except RuntimeError:
    check(True, "a wrong password is refused")

print("WORKSPACE OK")
