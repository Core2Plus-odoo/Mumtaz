# Jawhar public website — redesign

## 1. Information architecture

```
/                 Home: promise, four pillars, a day, interface, agents, rules, what's built, demo form
/apps/            Catalogue with truthful statuses
/modules/sales-hub/   Deep page per module (template for the others)
/intelligence/    Agents, governance, pricing shape (proposal)
/preview/         Interactive screen walkthrough
/pricing/         Placeholder until approved (banner stays)
/signup/          Setup wizard prototype (banner stays) → replaced by onboarding in Phase 4
/ar/…             Arabic site (Phase 2c)
```

## 2. Page spec: home (delivered in this slice)

| Section | Purpose | Truth source |
| --- | --- | --- |
| Hero | one promise, two CTAs, trust chips, AI-labelled hero image, price card from the demo DB | engine figures |
| Four pillars | each pillar lists 4 capabilities with readiness tags | `FEATURE_REGISTER.md` |
| A day in the boutique | four steps the software enforces | tests |
| The interface | five screenshots, each linked to the preview | demo DB |
| Intelligence | five agents with honest status | `policy.py` |
| Three rules | the enforced invariants | module docs |
| What's built | status table with the vocabulary defined above it, test count and date | CI run |
| Request a demo | functional form → CRM, consent sentence verbatim, e-mail fallback | `mumtaz_jewellery_website` |

## 3. Copy rules

- Never "coming soon" without a phase; never "offline" for the counter; never "Enterprise".
- Prices only with the placeholder banner until J-05.
- Test counts and dates are copied from the last green CI run and updated with each release.
- Every image that is not a product screenshot is labelled.
- Names on the site are synthetic.

## 4. Lead capture

Form fields: business, name, e-mail, phone (optional), country, stores,
focus (optional), consent (required), honeypot. POST
`/jawhar/public/site/demo-request`. Success shows the reference; failure
shows the server's message; network failure offers the e-mail fallback with
the typed details prefilled. Server: validation, per-contact daily cap
(default 3, `mumtaz_jewellery.demo_request_daily_cap`), lead tagged "Jawhar
demo", consent text and timestamp stored, nothing e-mailed automatically.

## 5. SEO and growth (Phase 2c, after the production domain decision)

Remove `noindex` on the production host only; sitemap; Organization and
SoftwareApplication structured data (home already carries the latter);
Arabic pages with `hreflang`; per-module landing pages; Core Web Vitals
budget (LCP < 2.5 s on 4G: hero image is 100 KB WebP with a 28 KB
small source).

## 6. Measurement

Demo requests per week (CRM tag), form error rate (server log), page weight
and LCP (Lighthouse in CI, PLANNED). No third-party analytics until a privacy
notice exists (J-06).

## 7. Done in this slice / next

Done: design system file, home rebuilt, six sub-pages rethemed and
corrected (stale statuses, offline claims, test counts), form live against
the new module, screenshots in the PR. Next: app palette migration, Arabic
home, module pages for Counter/Stores/Compliance, pricing from the control
plane once approved.
