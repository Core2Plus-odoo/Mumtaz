# Jawhar — development progress

Chronological. Each entry follows the mandatory report format.

## 2026-11-21 — Phase 0 audit + slice 2a (design system, public home, lead capture)

**TASK.** Evidence-based audit of jewel.mumtaz.digital and the repository; 17 documents; first safe slice: design system and public website with functional lead capture, preserving product functionality.

**REPOSITORY STATUS.** 13 Jawhar modules + demo on Odoo 19 CE, 242 Odoo tests green before the slice; React app 26 pages; static site 7 pages with stale statuses, an "offline" claim, mailto-only CTAs; platform tenancy/branding/control-plane modules present, install-tested only.

**PROCESS IMPACT.** Visitor → demo request → CRM lead (new). No business process in the tenant changes.

**PLAN.** Audit → register → documents → `site/jawhar.css` → home rebuilt → sub-pages rethemed and corrected → `mumtaz_jewellery_website` (model, public POST, tests) → nginx carve-out in repo → CI → screenshots → PR.

**IMPLEMENTED.**
- `docs/jawhar/*` (17 files).
- `website/jewel/site/jawhar.css` design system; `website/jewel/index.html` rebuilt (hero with AI-labelled image, pillars with readiness tags, day, interface, agents, rules, status table, functional form, footer, theme toggle, reveal with reduced-motion guard); six sub-pages rethemed (palette, serif display) and corrected (offline claims, "in development/planned" tags for built features, test counts, Rayan/Amara/Noor statuses).
- `addons/mumtaz_jewellery_website`: `jewellery.demo.request`, `create_public` (validation, consent, per-contact daily cap, lead tagged "Jawhar demo"), `/jawhar/public/site/demo-request` (honeypot, JSON errors), list/form views and CRM menu, 5 HTTP/ORM tests; registered in `scripts/jewel_ci.sh` and `deploy/jewel-staging/deploy.sh`.
- `deploy/jewel-staging/nginx/jewel.mumtaz.digital.conf`: `limit_req_zone` + `location ^~ /jawhar/public/site/` without basic auth (not applied).

**VERIFIED.**
- `scripts/jewel_ci.sh`: 19 pure-Python tests, 247 Odoo tests, 0 failures (fresh DB `jewel_ci_2645`).
- flake8 + pyflakes + `check_sudo.py` clean on the new module (4 labelled `sudo()`).
- Headless render of all 7 pages at 1440 and 390 px (home also dark): 0 page errors, 0 horizontal scroll, 0 failed requests, 0 broken images after lazy load. Form: blocked without consent by the browser; success path shows the reference; 400 path shows the server message; mobile menu toggles with `aria-expanded`.
- Not verified: the live endpoint on staging (nginx not applied; the page falls back to e-mail), the app with the new palette (Phase 2b), device tests.

**RECONCILIATION.** Site claims now match the register: counter online-only; tray, outreach, counter, client app, stores, AML all "Built & tested"; Noor "Device test pending"; Rayan/Amara "Specified only"; tests 266 as of this run.

**DECISIONS / BLOCKERS.** J-01, J-02, J-03, J-09, J-10 taken; J-12 (nginx apply), staging promotion, ElevenLabs tools, J-05/J-07/J-04 open. See `DECISION_REGISTER.md`.

**NEXT ACTION.** Human review and merge; user applies nginx and promotes staging per the runbook; then Phase 2b (app palette migration) on a new branch.

Screenshots for this slice: `docs/jawhar/screenshots/` (home desktop fold and
full page, home mobile, form success state, sub-page contact sheet).

## 2026-11-21 — Phase 2b: app palette migration, dark theme, kiosk unified

**TASK.** Bring the Jawhar React app onto design system v2 without changing behaviour.

**REPOSITORY STATUS.** App on v1 indigo tokens; kiosk on its own teal/gold set; no dark theme; display face sans everywhere.

**PROCESS IMPACT.** None: presentation only. No API, model or data change.

**PLAN.** Repoint the v1 token names to v2 values (components untouched) → add `[data-theme="dark"]` set → alias the kiosk `--k-*` tokens into the system, keeping deep emerald for white-on-colour surfaces → serif page title and wordmark → focus ring → theme toggle in the rail footer, remembered per browser and applied before first paint → verify in EN/AR × light/dark.

**IMPLEMENTED.** `apps/jawhar-web/src/styles.css` (token block, dark set, kiosk aliases, literals replaced by tokens, amber text token for dark readability), `index.html` (Cormorant Garamond), `components/Shell.tsx` (theme state and toggle), `lib/i18n.ts` (two keys, EN/AR), `main.tsx` (boot-time theme). Docs: `DESIGN_SYSTEM.md` §8, `DECISION_REGISTER.md` J-02, roadmap row 2b. Screenshots in `docs/jawhar/screenshots/app-*.jpg`.

**VERIFIED.** `tsc` clean; vitest 34/34; headless walk of 17 routes × EN/AR × light/dark (68 loads) against the demo database: 0 page errors, 0 horizontal overflow, `dir` and `data-theme` correct on every load; kiosk and login shot in both themes. Not verified: tablet ergonomics on a device; contrast audit by tool (manual check of the main pairs only).

**RECONCILIATION.** Site and app now share one palette, one display face and one readiness vocabulary; the kiosk no longer carries a third theme.

**DECISIONS / BLOCKERS.** None new. Density on Today and empty states move to Phase 3 with the command centre.

**NEXT ACTION.** Human review and merge; staging promotion (user); then Phase 2c (Arabic site, module pages) or Phase 3 (command centre) on your call.
