"""AS-IS field inventory, parsed with ast (no imports, nothing executes).

Emits one CSV row per declared field with the governance columns the blueprint
§7.4 data dictionary requires. Columns we cannot derive from code are left
empty on purpose rather than guessed.
"""
import ast, csv, os, sys

ROOT, OUT = sys.argv[1], sys.argv[2]
COLS = ["module","model","model_kind","technical_name","label","data_type",
        "required","readonly","compute","store","related","reference_model",
        "selection_values","groups","company_scope","tracking","index","default",
        "security_class","source_of_truth","audit_policy","test_id"]

def const(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None

rows = []
for mod in sorted(os.listdir(ROOT)):
    md = os.path.join(ROOT, mod)
    if not os.path.isdir(md):
        continue
    for dp, dn, fns in os.walk(md):
        dn[:] = [d for d in dn if d not in {"__pycache__", "tests"}]
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dp, fn)
            try:
                tree = ast.parse(open(fp, encoding="utf-8", errors="replace").read())
            except SyntaxError:
                continue
            for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                kind = ""
                for b in cls.bases:
                    if isinstance(b, ast.Attribute):
                        kind = b.attr
                if kind not in {"Model", "AbstractModel", "TransientModel"}:
                    continue
                mname = inh = ""
                for st in cls.body:
                    if isinstance(st, ast.Assign) and len(st.targets) == 1 \
                       and isinstance(st.targets[0], ast.Name):
                        t = st.targets[0].id
                        if t == "_name":
                            mname = const(st.value) or ""
                        elif t == "_inherit":
                            v = const(st.value)
                            inh = v if isinstance(v, str) else (v[0] if isinstance(v, list) and v else "")
                model = mname or inh
                if not model:
                    continue
                for st in cls.body:
                    if not (isinstance(st, ast.Assign) and len(st.targets) == 1
                            and isinstance(st.targets[0], ast.Name)):
                        continue
                    name = st.targets[0].id
                    call = st.value
                    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                            and isinstance(call.func.value, ast.Name)
                            and call.func.value.id == "fields"):
                        continue
                    kw = {k.arg: k.value for k in call.keywords if k.arg}
                    pos = const(call.args[0]) if call.args else None
                    ftype = call.func.attr
                    comodel = const(kw.get("comodel_name")) if "comodel_name" in kw else (
                        pos if ftype in {"Many2one","One2many","Many2many"} and isinstance(pos,str) else "")
                    label = const(kw.get("string")) if "string" in kw else (
                        pos if ftype not in {"Many2one","One2many","Many2many"} and isinstance(pos,str) else "")
                    sel = ""
                    if "selection" in kw:
                        v = const(kw["selection"])
                        if isinstance(v, list):
                            sel = "|".join(str(x[0]) for x in v if isinstance(x,(list,tuple)) and x)
                    rows.append({
                        "module": mod, "model": model,
                        "model_kind": ("new" if mname else "inherit:" + inh) + ("/" + kind if kind!="Model" else ""),
                        "technical_name": name, "label": label or "", "data_type": ftype,
                        "required": const(kw.get("required")) if "required" in kw else "",
                        "readonly": const(kw.get("readonly")) if "readonly" in kw else "",
                        "compute": const(kw.get("compute")) if "compute" in kw else "",
                        "store": const(kw.get("store")) if "store" in kw else "",
                        "related": const(kw.get("related")) if "related" in kw else "",
                        "reference_model": comodel or "",
                        "selection_values": sel,
                        "groups": const(kw.get("groups")) if "groups" in kw else "",
                        "company_scope": "company_dependent" if const(kw.get("company_dependent")) else "",
                        "tracking": const(kw.get("tracking")) if "tracking" in kw else "",
                        "index": const(kw.get("index")) if "index" in kw else "",
                        "default": ("<callable>" if isinstance(kw.get("default"), (ast.Lambda, ast.Attribute, ast.Name))
                                    else (const(kw.get("default")) if "default" in kw else "")),
                        "security_class": "", "source_of_truth": "", "audit_policy": "", "test_id": "",
                    })

with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=COLS)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"fields={len(rows)} models={len({r['model'] for r in rows})}")
