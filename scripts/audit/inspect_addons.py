"""Static inventory of the Odoo addons in this repo. Read-only: parses source,
never imports it, so nothing from the tree executes."""
import ast, json, os, re, sys

ROOT = sys.argv[1]
RISK = {
    "sudo":        re.compile(r"\.sudo\(\)"),
    "raw_sql":     re.compile(r"self\._?cr\.execute|self\.env\.cr\.execute"),
    "float_money": re.compile(r"fields\.Float\([^)]*(amount|price|total|cost|balance)", re.I),
    "attrs":       re.compile(r'\battrs\s*='),
    "tree_view":   re.compile(r"<tree[\s>]"),
    "states_attr": re.compile(r'\bstates\s*=\s*\{'),
}
POSTING = re.compile(r"account\.move|stock\.move|account\.payment|_post\(\)|action_post")

def manifest(p):
    try:
        return ast.literal_eval(open(os.path.join(p, "__manifest__.py")).read())
    except Exception as exc:
        return {"__error__": str(exc)}

def scan(mod_dir):
    out = {
        "models": [], "inherits": [], "py_files": 0, "py_lines": 0,
        "xml_files": 0, "csv_acl": [], "record_rules": 0, "groups": 0,
        "tests": 0, "test_files": [], "owl_js": 0, "qweb_reports": 0,
        "risk": {k: 0 for k in RISK}, "posting_hits": 0, "constraints": 0,
    }
    for dirpath, dirnames, filenames in os.walk(mod_dir):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, mod_dir)
            try:
                src = open(fp, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if fn.endswith(".py"):
                out["py_files"] += 1
                out["py_lines"] += src.count("\n") + 1
                if "/tests/" in "/" + rel or rel.startswith("tests"):
                    out["test_files"].append(rel)
                    out["tests"] += len(re.findall(r"def test_", src))
                for m in re.finditer(r'_name\s*=\s*[\'"]([^\'"]+)', src):
                    out["models"].append(m.group(1))
                for m in re.finditer(r'_inherit\s*=\s*[\'"]([^\'"]+)', src):
                    out["inherits"].append(m.group(1))
                out["constraints"] += len(re.findall(r"@api\.constrains|models\.Constraint", src))
                for k, rx in RISK.items():
                    out["risk"][k] += len(rx.findall(src))
                out["posting_hits"] += len(POSTING.findall(src))
            elif fn.endswith(".xml"):
                out["xml_files"] += 1
                out["record_rules"] += len(re.findall(r'model="ir\.rule"', src))
                out["groups"] += len(re.findall(r'model="res\.groups"', src))
                out["qweb_reports"] += len(re.findall(r'model="ir\.actions\.report"|<template[^>]*report', src))
                for k, rx in RISK.items():
                    if k in ("tree_view", "attrs", "states_attr"):
                        out["risk"][k] += len(rx.findall(src))
            elif fn.endswith(".csv") and "ir.model.access" in fn:
                rows = [r for r in src.splitlines()[1:] if r.strip()]
                out["csv_acl"].append({"file": rel, "rows": len(rows)})
            elif fn.endswith(".js"):
                out["owl_js"] += 1
    return out

result = {}
for name in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, name)
    if not os.path.isdir(d):
        continue
    info = scan(d)
    info["manifest"] = manifest(d)
    result[name] = info
print(json.dumps(result, indent=1))
