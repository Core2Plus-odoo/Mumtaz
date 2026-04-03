#!/usr/bin/env python3
"""Run Odoo module upgrade migration for selected DB/module list."""
from __future__ import annotations

import argparse
import os
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.getenv("ODOO_DB_NAME", "mumtaz"))
    parser.add_argument("--config", default="/etc/odoo/odoo.conf")
    parser.add_argument("--modules", default="base")
    args = parser.parse_args()

    cmd = [
        "odoo",
        "-c",
        args.config,
        "-d",
        args.db,
        "-u",
        args.modules,
        "--stop-after-init",
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
