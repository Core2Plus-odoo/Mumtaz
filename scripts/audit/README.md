# Static audit scripts

Read-only inventory tools for the addons tree. They
parse source with `ast` and regex and never import the code they inspect, so
nothing in `addons/` executes.

```bash
python3 -I scripts/audit/inspect_addons.py addons > /tmp/addons.json   # module inventory + risk flags
python3 -I scripts/audit/acl_coverage.py   addons > /tmp/acl.json      # per-model ACL / ir.rule coverage
python3 -I scripts/audit/fields.py         addons /tmp/fields.csv
```

`acl_coverage.py` is deliberately v2: the first version matched `_rec_name`,
`brand_name` and `company_name` with a loose `_name\s*=` regex and invented models
that do not exist. The match is now anchored to the start of a line. If you extend
these scripts, re-check a finding by hand before reporting it.
