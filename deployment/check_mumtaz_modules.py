#!/usr/bin/env python3
"""Quick local check that Mumtaz addons are structurally discoverable by Odoo."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["mumtaz_base", "mumtaz_core", "mumtaz_ai"]

errors = []
for mod in MODULES:
    mp = ROOT / mod / "__manifest__.py"
    ip = ROOT / mod / "__init__.py"
    if not mp.exists():
        errors.append(f"Missing manifest: {mp}")
    if not ip.exists():
        errors.append(f"Missing __init__: {ip}")

if errors:
    print("FAILED")
    for e in errors:
        print(f"- {e}")
    raise SystemExit(1)

print("OK: all Mumtaz modules have __manifest__.py and __init__.py")
