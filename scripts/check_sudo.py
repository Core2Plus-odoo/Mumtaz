#!/usr/bin/env python3
"""Every sudo() in the addons must say why.

Backlog item 3 of docs/erp/BACKLOG.md. A `sudo()` widens access past the
signed-in user's rights, so each call site carries a justification comment
of the form `# sudo: <reason>` on the same line or the line above. Reasons
that start with `REVIEW-` name an open item in
docs/erp/architecture/SECURITY_MATRIX.md and are accepted by this check but
must be closed by the programme.

Usage: scripts/check_sudo.py [addons-dir]   (exit 1 lists every unlabelled site)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "addons")
LABEL = re.compile(r"#\s*sudo:\s*\S")
CALL = re.compile(r"\bsudo\(")


def main():
    bad = []
    total = 0
    for path in sorted(ROOT.rglob("*.py")):
        parts = path.parts
        if "tests" in parts or "__pycache__" in parts or "migrations" in parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            code = line.split("#", 1)[0]
            if not CALL.search(code):
                continue
            total += 1
            above = lines[i - 1] if i else ""
            if LABEL.search(line) or LABEL.search(above):
                continue
            bad.append(f"{path}:{i + 1}: {line.strip()[:110]}")
    if bad:
        print(f"{len(bad)} of {total} sudo() calls carry no '# sudo: <reason>' label:")
        print("\n".join(bad))
        return 1
    print(f"OK: all {total} sudo() calls are labelled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
