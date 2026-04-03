#!/usr/bin/env python3
"""Validate deployment preconditions and key files."""
from pathlib import Path

required_files = [
    Path("docker-compose.production.yml"),
    Path(".env.production"),
    Path("config/odoo.conf"),
    Path("scripts/health-check.sh"),
]

missing = [str(p) for p in required_files if not p.exists()]
if missing:
    print("Missing required deployment files:")
    for m in missing:
        print(f" - {m}")
    raise SystemExit(1)

print("Deployment validation passed.")
