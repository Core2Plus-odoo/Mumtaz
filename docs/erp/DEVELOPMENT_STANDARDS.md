# 7. Development standards and coding conventions

These restate the blueprint pack's `CLAUDE.md` guardrails as this
repository's conventions. They apply to every addon under `addons/` and to
the connected applications. The Jawhar rules in `docs/mumtaz-jewel/CLAUDE.md`
remain in force and are stricter on deploys and compliance values.

## 7.1 Process for every task (Analyse → Design → Validate dependencies → Implement → Test → Reconcile → Document → Report)

1. **Inspect** the module, its tests, its spec in `docs/erp/modules/`, the decision register and the data dictionary before writing code.
2. **Map the impact**: entities, states, links, posting, stock, permissions, integrations, reports, regression tests.
3. **Plan the smallest vertical slice** that works end to end (upstream and downstream link), with files, data migration, tests and rollback.
4. **Implement** server-side rules; reuse the standard app; no duplicate masters; `company_id` on every new model.
5. **Verify** with the real suite on a disposable database; record commands and results; `NOT RUN` is a valid, honest status.
6. **Reconcile** money and stock effects where touched.
7. **Document**: module spec, data dictionary rows, decision register, test matrix, changelog (`docs/mumtaz-jewel/PLAN_V3_RECONCILIATION.md` for Jawhar, `docs/erp/quality/RELEASE_CHANGELOG.md` for the rest).
8. **Report** in the mandatory format (below).

## 7.2 Mandatory report format for development work

```
TASK: <ID and one-sentence outcome>
REPOSITORY STATUS: <existing capability found / gaps>
PROCESS IMPACT: <upstream / downstream / finance / inventory / security>
PLAN: <minimal vertical slice, files, migration, tests>
IMPLEMENTED: <actual changes, filenames and commit if any>
VERIFIED: <commands run and observed results; NOT RUN when applicable>
RECONCILIATION: <source-to-destination or ledger checks, if relevant>
DECISIONS/BLOCKERS: <approved, assumptions, pending>
NEXT ACTION: <one concrete action or approval>
```

## 7.3 Odoo module conventions [VERIFIED as practised by the Jawhar modules; required everywhere]

| Rule | Detail |
| --- | --- |
| Manifest | `version` `19.0.x.y.z`; `license` `LGPL-3`; `depends` minimal and explicit; `data` lists security before views; `installable: True` |
| Layout | `models/`, `controllers/`, `security/{security.xml, ir.model.access.csv}`, `data/`, `views/`, `tests/`, `README.md`; one model per file |
| Models | `_name` with product prefix (`jewellery.`, `c2p.`, `mumtaz.`); `_description`; `company_id` required with default; `mail.thread` + `tracking=True` on state and money fields of transactional models; `Monetary` for money, `Float` with `digits` for weights |
| State | `state` Selection; transitions only through `action_*` methods that check rights, guards and SoD; `UserError` with a sentence a user understands |
| Security | groups in `security.xml`; access CSV for every model; record rules per company and per role; `sudo()` only with `# sudo: <reason>`; public controllers read narrow, serial-addressed data and never return internal ids |
| Money and rates | prices come from one engine (Jawhar) or standard pricelists; snapshot the rate on the line; never recompute after confirmation |
| Concurrency | row lock on commit paths (`SELECT … FOR UPDATE`), one live order per serial, idempotent webhooks keyed on the provider's event id |
| Migrations | additive fields with defaults may rely on `-u`; any rename, type change or data move gets `migrations/<version>/pre-,post-migrate.py` and a test on a database with data |
| Tests | `TransactionCase` for rules, `HttpCase` for doors; tags `post_install`; synthetic data only (`TEST`/`DEMO` prefixes); every slice adds positive, negative (wrong role, wrong company), edge and idempotency tests; fresh-database install in CI |
| No | direct SQL (except a reviewed patch), forks of core, writes to posted moves, `print`, secrets in code or XML, real client data |

## 7.4 Python and JavaScript style [VERIFIED tooling]

- Python: `flake8` + `bugbear` (`.flake8` at root), `bandit`, `pyflakes` locally; docstrings in plain sentences saying why.
- TypeScript (Jawhar): `tsc --noEmit`, `vitest`, Vite build; one i18n dictionary (EN/AR), no duplicate keys (checked); public routes exact-matched.
- Commit messages: what and why in sentences; PR body with "What" and "Tests" (commands and counts).
- Branch names `claude/<product>-<slice>`; `main` deploys production for the C2P console; Jawhar staging promotes from `main` by hand.

## 7.5 Definition of ready and done

**Ready**: requirement id and owner; entity/field rows; state table; role matrix; posting/stock effect; acceptance tests written as GIVEN/WHEN/THEN.

**Done**: code reviewed; install + upgrade on a fresh database green; positive, negative and cross-company tests green; posting and stock reconcile where touched; list/form/API usable; empty and error states; docs updated (spec, dictionary, changelog); evidence (commands, counts, screenshots of walks) in the PR; business owner accepts. A rendered screen or a green unit suite alone is not done.

## 7.6 Prohibited shortcuts

Skipping, disabling or quarantining tests to go green; empty commits to kick
CI; writing to production; deleting data; inventing tax, AML, payroll or
retention values; turning an AI suggestion into an irreversible action
without a named approval; claiming a test passed that did not run.
