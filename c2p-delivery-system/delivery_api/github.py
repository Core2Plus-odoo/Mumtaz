"""GitHub addons-repo bridge — push generated Odoo modules to the repo that
Odoo.sh (or any Odoo) builds from.

The connection (repo URL, branch, token) comes from the encrypted app settings
via a provider the app sets, falling back to env. The token authenticates an
HTTPS push and is decrypted only at call time. The token is NEVER returned to a
client and is scrubbed from any error text before it leaves this module.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional
from urllib.parse import quote, urlparse

_log = logging.getLogger("c2p.github")

# Resolver set by the app: returns {"repo","branch","token","subdir"} or {}.
CONN_PROVIDER = None


def _settings() -> dict:
    if CONN_PROVIDER:
        try:
            return CONN_PROVIDER() or {}
        except Exception:
            return {}
    return {}


def configured() -> bool:
    s = _settings()
    return bool(s.get("repo") and s.get("token"))


def _auth_url(repo: str, token: str) -> str:
    """Embed the token into the HTTPS clone URL (GitHub accepts a PAT as the
    username via the x-access-token convention)."""
    u = urlparse(repo if "://" in repo else "https://" + repo)
    host = u.hostname or "github.com"
    path = u.path
    if not path.endswith(".git"):
        path = path.rstrip("/") + ".git"
    return f"https://x-access-token:{quote(token, safe='')}@{host}{path}"


def _scrub(text: str, token: str | None) -> str:
    """Remove the token (and the x-access-token prefix) from any text."""
    t = text or ""
    if token:
        t = t.replace(token, "***").replace(quote(token, safe=""), "***")
    return t.replace("x-access-token:***@", "").replace("x-access-token", "")


def _run(args, token, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        msg = _scrub((r.stderr or r.stdout or "git error").strip(), token)
        raise RuntimeError(msg[:400])
    return r


def _safe_join(base: str, rel: str) -> Optional[str]:
    rel = (rel or "").lstrip("/")
    dest = os.path.normpath(os.path.join(base, rel))
    base_n = os.path.normpath(base)
    if dest == base_n or dest.startswith(base_n + os.sep):
        return dest
    return None


def _redact_repo(repo: str) -> str:
    u = urlparse(repo if "://" in repo else "https://" + repo)
    return f"{u.hostname or ''}{u.path}"


def test_connection() -> dict:
    """Verify the repo + token by listing remote branches (no write)."""
    s = _settings()
    repo, token = s.get("repo"), s.get("token")
    if not repo or not token:
        raise RuntimeError("Set the GitHub repository and a token first.")
    url = _auth_url(repo, token)
    r = _run(["git", "ls-remote", "--heads", url], token, timeout=30)
    branches = [ln.split("refs/heads/", 1)[-1]
                for ln in r.stdout.splitlines() if "refs/heads/" in ln]
    return {"ok": True, "repo": _redact_repo(repo), "branches": branches}


def push_module(name: str, files: list, message: str | None = None) -> dict:
    """Clone the configured branch, write the module under the optional subdir,
    commit and push. Returns a redacted result; raises RuntimeError (scrubbed)
    on failure."""
    s = _settings()
    repo, token = s.get("repo"), s.get("token")
    branch = s.get("branch") or "main"
    subdir = (s.get("subdir") or "").strip("/")
    if not repo or not token:
        raise RuntimeError("GitHub repository is not configured.")
    url = _auth_url(repo, token)
    work = tempfile.mkdtemp(prefix="c2p_gh_")
    try:
        _run(["git", "clone", "--depth", "1", "--branch", branch, url, work],
             token, timeout=180)
        base = os.path.join(work, subdir) if subdir else work
        moddir = os.path.join(base, name)
        written = []
        for f in files or []:
            dest = _safe_join(moddir, f.get("path") or "")
            if not dest:
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(f.get("content") or "")
            written.append(os.path.relpath(dest, moddir))
        _run(["git", "-C", work, "add", "-A"], token, timeout=60)
        commit = subprocess.run(
            ["git", "-C", work, "-c", "user.email=bot@core2plus.com",
             "-c", "user.name=C2P Bot", "commit", "-m",
             message or f"Deploy module {name}"],
            capture_output=True, text=True, timeout=60)
        blob = (commit.stdout + commit.stderr).lower()
        if commit.returncode != 0 and "nothing to commit" in blob:
            return {"module": name, "files": len(written), "pushed": False,
                    "branch": branch, "repo": _redact_repo(repo),
                    "note": "no changes to push"}
        if commit.returncode != 0:
            raise RuntimeError(_scrub(commit.stderr or "commit failed", token)[:400])
        _run(["git", "-C", work, "push", "origin", branch], token, timeout=180)
        return {"module": name, "files": len(written), "pushed": True,
                "branch": branch, "repo": _redact_repo(repo),
                "written": written}
    finally:
        shutil.rmtree(work, ignore_errors=True)
