# Jawhar — test and acceptance plan

## 1. Layers

| Layer | What | How | Gate |
| --- | --- | --- | --- |
| Lint | flake8 (max 120), pyflakes, `scripts/check_sudo.py` | `ci.yml` lint job | every PR |
| Engine unit | pricing, fit library | `unittest` (19), vitest | every PR |
| Odoo install + tests | 14 Jawhar modules on a fresh DB, 247 tests (`post_install`) | `scripts/jewel_ci.sh` (`KEEP_DB=0 PGHOST=… ODOO_PATH=… JEWEL_TEST_HTTP_PORT=8097`) | every PR |
| HTTP boundary | API door, public doors (kiosk, client, website) | `HttpCase` | every PR |
| Front end | tsc, vitest, headless walks EN/AR with mocked API | `apps/jawhar-web` scripts | app PRs |
| Site | render at 1440/390, light/dark, no console errors, no horizontal scroll, no 4xx, form success/error paths against a mocked endpoint | `$S/shoot-v2.js` pattern (to move into `scripts/site_check.js`) | site PRs |
| Platform install | all non-Jawhar addons install | `scripts/platform_ci.sh` | platform PRs |
| Staging smoke | `deploy/jewel-staging/verify_site.sh`, health endpoint, login, counter commit on demo data | after each promotion | user runs |
| Device | camera try-on on a tablet, live voice session, counter on the till hardware | manual script in `docs/mumtaz-jewel/` (to write) | before pilot |
| Security | negative tests per module (cross-company, restricted, share users); pen test | tests in CI; pen test PLANNED | before production |
| Performance | counter commit, list pages at 50k pieces | k6 or locust script PLANNED | before production |

## 2. Acceptance per phase (summary)

- 2a (this PR): every page renders at both widths and both schemes without errors; every readiness label matches `FEATURE_REGISTER.md`; a demo request with consent creates a tagged lead and returns only a reference; one without consent is refused; a bot that fills the honeypot is told thank you and nothing is written; the fourth request from one address in a day is refused.
- 2b: app walks green in EN and AR with the new tokens; no contrast below 4.5:1 for text.
- 3: each command-centre figure opens its source records; tests prove the sum.
- 4: second-tenant acceptance (`WHITE_LABEL_SPECIFICATION.md` §6); no cross-tenant read by host or id.
- 5: golden set per agent passes; a restricted field never appears in a captured prompt.
- 10: restore drill from last night's backup on a clean host within the agreed RTO.

## 3. How to run locally

```bash
KEEP_DB=0 PGHOST=/home/odoopg/sock PGUSER=odoo ODOO_PATH=$S/odoo19 JEWEL_TEST_HTTP_PORT=8097 LOG_DIR=$S/ci bash scripts/jewel_ci.sh
```

```bash
python3 scripts/check_sudo.py addons && flake8 addons/
```

## 4. Rules

Never claim a test passed that did not run; every PR quotes the CI totals; a skipped or disabled test is a finding, not a fix.
