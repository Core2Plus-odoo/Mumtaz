"""Per-model ACL / record-rule coverage.

v2: the v1 regex `_name\s*=` also matched `_rec_name`, `brand_name`,
`company_name` and friends, which invented models that do not exist. Anchor
the match to the start of the line so only a real `_name =` counts.
"""
import os, re, sys, csv, io, json
ROOT = sys.argv[1]
RE_NAME = re.compile(r'^\s*_name\s*=\s*[\'"]([a-z0-9_.]+)[\'"]', re.M)
RE_INH  = re.compile(r'^\s*_inherit\s*=\s*[\'"]([a-z0-9_.]+)[\'"]', re.M)
RE_INHL = re.compile(r'^\s*_inherit\s*=\s*\[([^\]]+)\]', re.M)
rows = []
for mod in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, mod)
    if not os.path.isdir(d):
        continue
    models, inherits, acl, rules, abstract = set(), set(), set(), set(), set()
    for dp, dn, fns in os.walk(d):
        dn[:] = [x for x in dn if x not in {".git", "__pycache__"}]
        for fn in fns:
            fp = os.path.join(dp, fn)
            try:
                src = open(fp, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if fn.endswith(".py") and "/tests" not in fp:
                found = set(RE_NAME.findall(src))
                models |= found
                inherits |= set(RE_INH.findall(src))
                for blk in RE_INHL.findall(src):
                    inherits |= set(re.findall(r'[\'"]([a-z0-9_.]+)[\'"]', blk))
                # AbstractModel / TransientModel need no ir.model.access row
                for cls in re.findall(r'class\s+\w+\(models\.(\w+)\).*?(?=\nclass |\Z)', src, re.S):
                    pass
                for m in re.finditer(r'class\s+\w+\(models\.(AbstractModel|TransientModel)\)(.*?)(?=\nclass |\Z)', src, re.S):
                    abstract |= set(RE_NAME.findall(m.group(2)))
            if fn.endswith(".csv") and "access" in fn:
                for r in csv.DictReader(io.StringIO(src)):
                    mid = (r.get("model_id:id") or r.get("model_id/id") or "").strip()
                    if ".model_" in mid:
                        acl.add(mid.split(".model_", 1)[1])
                    elif mid.startswith("model_"):
                        acl.add(mid[len("model_"):])
            if fn.endswith(".xml"):
                for blk in re.findall(r'<record[^>]*model="ir\.rule".*?</record>', src, re.S):
                    m = re.search(r'name="model_id"\s+ref="(?:[\w.]*\.)?model_([a-z0-9_]+)"', blk)
                    if m:
                        rules.add(m.group(1))
    norm = lambda s: s.replace(".", "_")
    concrete = {norm(m) for m in models} - {norm(m) for m in abstract}
    if models:
        rows.append({
            "module": mod,
            "models": sorted(norm(m) for m in models),
            "abstract": sorted(norm(m) for m in abstract),
            "concrete": sorted(concrete),
            "no_acl": sorted(concrete - acl),
            "no_rule": sorted(concrete - rules),
            "inherits": sorted(inherits),
        })
print(json.dumps(rows, indent=1))
