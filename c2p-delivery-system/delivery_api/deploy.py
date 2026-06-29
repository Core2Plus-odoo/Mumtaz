"""Module deploy — write a generated Odoo module to the account's addons repo.

Gated by the approval layer (action `code_deploy`): nothing reaches a repo
until a human approves. **Staged by default** — with no repo configured the
module is written to a staging directory on the server and reported, nothing is
pushed. Configure a checked-out addons repo to go live:

  C2P_ADDONS_DIR   path to a git working copy whose remote can be pushed
  C2P_DEPLOY_LIVE  "1" to actually git add/commit/push (Odoo.sh then builds)
  C2P_DEPLOY_BRANCH branch to push (default "main")

The call site is identical for staged vs live; only the env differs.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

_log = logging.getLogger("c2p.deploy")


def _slug(name: str | None) -> str:
    s = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in (name or "module"))
    return s.strip("_") or "module"


def _safe_join(base: str, rel: str) -> str | None:
    """Join base + rel, refusing anything that escapes base (path traversal)."""
    rel = (rel or "").lstrip("/")
    dest = os.path.normpath(os.path.join(base, rel))
    base_n = os.path.normpath(base)
    if dest == base_n or dest.startswith(base_n + os.sep):
        return dest
    return None


def deploy_module(developer_output: dict, module_name: str | None = None) -> dict:
    name = _slug(module_name or developer_output.get("module_technical_name") or "module")
    files = developer_output.get("files") or []

    addons_dir = os.environ.get("C2P_ADDONS_DIR")
    live = bool(addons_dir) and os.environ.get("C2P_DEPLOY_LIVE") == "1"
    root = addons_dir if live else os.path.join(tempfile.gettempdir(), "c2p_deploy")
    module_dir = os.path.join(root, name)

    written, skipped = [], []
    for f in files:
        dest = _safe_join(module_dir, f.get("path") or "")
        if not dest:
            skipped.append(f.get("path"))
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(f.get("content") or "")
        written.append(os.path.relpath(dest, module_dir))

    result = {"module": name, "files": len(written), "skipped": skipped,
              "path": module_dir, "mode": "live" if live else "staged",
              "pushed": False}

    if live:
        branch = os.environ.get("C2P_DEPLOY_BRANCH", "main")
        try:
            subprocess.run(["git", "-C", addons_dir, "add", "-A"], check=True, timeout=60)
            subprocess.run(["git", "-C", addons_dir,
                            "-c", "user.email=bot@core2plus.com",
                            "-c", "user.name=C2P Bot",
                            "commit", "-m", f"Deploy module {name}"], check=True, timeout=60)
            subprocess.run(["git", "-C", addons_dir, "push", "origin", branch],
                           check=True, timeout=120)
            result["pushed"] = True
        except Exception as exc:  # noqa: BLE001 - surface, don't crash the request
            _log.exception("git push failed for module %s", name)
            result["error"] = str(exc)
    return result
