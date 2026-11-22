# registry

`classification.json` is the hand-maintained source: one entry per Odoo
module with its layer (foundation, platform, product, edition, internal,
venture), a disposition and a note, plus the list of known layering
violations.

`registry.yaml` at the repository root is **generated** from it and from the
module manifests. Never edit it by hand:

```bash
python3 scripts/module_registry.py --write   # after adding or changing a module
python3 scripts/module_registry.py --check   # what CI runs
```

A new module that is not classified here fails CI. Proposed extensions
(owner, install profiles, more checks): `docs/platform/MUMTAZ_MODULE_REGISTRY_REVIEW.md`.
