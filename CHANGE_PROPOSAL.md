# Mumtaz — Suggested Next Changes (Post Reorganization)

Date: 2026-04-02

## 1) High-Impact Product Changes (Recommended First)

1. **Homepage visual credibility upgrade (V5)**
   - Replace placeholder KPI cards with realistic dashboard snapshots exported from real Odoo demo data.
   - Add enterprise logos/testimonials section with compliance-friendly wording.
   - Add GCC-focused value proposition strip (UAE/KSA/Qatar localization readiness).

2. **Add a dedicated "Platform Architecture" page**
   - Show clean architecture diagram: `Frontend -> API Gateway -> Odoo Addons -> Data & Integrations`.
   - Explain multi-tenant control plane (`mumtaz_tenant_manager`) and security boundaries.

3. **Create ROI-oriented pages for decision-makers**
   - `/for-cfo`, `/for-coo`, `/for-bank-partner` with metrics and use-case narratives.

## 2) Odoo Architecture Improvements

1. **Add integration API module**
   - New addon proposal: `mumtaz_api_gateway`
   - Responsibilities:
     - token-based auth for partners
     - versioned endpoints (`/api/v1/...`)
     - usage logging/rate-limit hooks

2. **Centralize shared service contracts**
   - Add a common service layer (interfaces + DTOs) to reduce duplication across:
     - `mumtaz_ai`
     - `mumtaz_voice`
     - `mumtaz_lead_nurture`
     - `mumtaz_lead_scraper`

3. **Tenant-safe configuration controls**
   - Strengthen tenant-isolation checks in `mumtaz_tenant_manager` workflows.
   - Add smoke test script to validate module bundles per tenant profile.

## 3) DevOps and Delivery Changes

1. **Add CI workflow** (`.github/workflows/ci.yml`)
   - Python compile check for `addons/` + `tools/`
   - Shell lint/syntax check for `ops/deployment/*.sh`
   - HTML/CSS sanity checks for `apps/website`

2. **Add CD workflow for static website**
   - GitHub Actions deploy to Hostinger via SFTP/SSH on tagged releases.

3. **Environment templates**
   - Add `.env.example` files for:
     - scraper runtime (`tools/scrapers/pakistan_trade_portal`)
     - AI provider keys
     - Odoo integration endpoints

## 4) Website Conversion & SEO Changes

1. **Technical SEO**
   - Add JSON-LD structured data for `SoftwareApplication` and `Organization`.
   - Generate sitemap.xml + robots.txt.

2. **Conversion optimization**
   - Add sticky CTA on mobile.
   - Add short lead form above fold for banking partners.
   - Add case-study section with quantifiable outcomes.

3. **Content system readiness**
   - Prepare migration path to Next.js + headless CMS if content velocity increases.

## 5) Security & Compliance Changes

1. **Secrets and key handling**
   - Introduce centralized secret management policy for API keys and webhook tokens.

2. **Audit and access logging**
   - Add structured audit events for sensitive actions across AI and tenant provisioning.

3. **Compliance posture docs**
   - Add a short `docs/security/compliance.md` covering data residency and logging controls for GCC enterprise buyers.

## 6) Proposed 30-Day Execution Plan

### Week 1
- CI baseline + shell/python/html checks
- SEO baseline (sitemap + robots + meta consistency)

### Week 2
- Architecture page + role-based landing pages
- Replace placeholder website visuals with product-true visuals

### Week 3
- Start `mumtaz_api_gateway` addon scaffolding + API versioning
- Add basic partner-auth endpoints

### Week 4
- Tenant smoke tests + release checklist
- Hostinger auto-deploy workflow from GitHub tags

## Success Metrics

- Website demo-request conversion rate improves by 20%+
- Deployment lead time reduced to <15 minutes with CI/CD
- API onboarding time for a new partner reduced by 30%+
- Zero broken links / page-level SEO errors on production scans
