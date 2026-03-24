#!/usr/bin/env python3
"""Quick local check that Mumtaz addons are structurally discoverable by Odoo."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Ordered by dependency chain — core first, then dependent modules
MODULES = [
    # Foundation layer
    "mumtaz_base",
    "mumtaz_core",
    # Brand / profile layer
    "mumtaz_branding",
    "mumtaz_sme_profile",
    "mumtaz_onboarding",
    # AI / Voice layer
    "mumtaz_ai",
    "mumtaz_voice",
]

errors = []
for mod in MODULES:
    mod_path = ROOT / mod
    if not mod_path.is_dir():
        errors.append(f"Missing module directory: {mod_path}")
        continue
    for required_file in ("__manifest__.py", "__init__.py"):
        if not (mod_path / required_file).exists():
            errors.append(f"Missing {required_file}: {mod_path / required_file}")

if errors:
    print("FAILED — structural issues found:")
    for e in errors:
        print(f"  - {e}")
    raise SystemExit(1)

print(f"OK — all {len(MODULES)} Mumtaz modules have __manifest__.py and __init__.py")
for mod in MODULES:
    print(f"  ✓ {mod}")
