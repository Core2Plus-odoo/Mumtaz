# Mumtaz Digital — Native Odoo 19 Website Builder Edition

This is a **different** addon from the earlier `mumtaz_website` prototype. It builds the approved compact Mumtaz homepage **inside Odoo's normal Website application** and is editable in the Website Builder.

## Critical differences from the previous prototype

- **Odoo Website app is required and used** (`website` + `website_crm`). No standalone HTML site, no external website framework, no custom controller.
- Uses Odoo's own `website.page` with `website.layout` — **standard Odoo header, footer, menus, page settings, translations and edit button remain available**.
- All page content is **literal, editable snippet markup** under `#wrap.oe_structure`; it is not merely one large custom QWeb component or a `t-call` to immutable static templates.
- Seven customizable blocks (hero, routing cards, platform, editions, ZAKI, partners, native CRM form) appear in the **Website Builder > Blocks > Mumtaz Digital** library, with local thumbnails. You can drag in, duplicate, delete, reorder and edit the text/images/buttons using Website editor.
- Uses **Odoo Website Form**, configured for CRM opportunities (`website_crm`) rather than custom lead-handling Python.
- CSS is scoped to `.o_mumtaz_site` so other Odoo websites, including IG2 and C2P, are not restyled.
- Installation only adds an **unpublished** preview page at `/mumtaz-native-preview`. It never changes `/` or the active homepage and does not create global menu entries.

## Installation

1. Unzip into your Odoo 19 Community custom `addons_path` so that the folder is `mumtaz_website_builder/`.
2. Use a **staging database first**. Install the normal Website and CRM modules (or let module dependencies install `website` and `website_crm`).
3. Restart Odoo, update the Apps list, install **Mumtaz Digital - Native Website Builder Blocks**.
4. As a website administrator, visit `/mumtaz-native-preview` and click **Edit**. Its sections should be editable and the **Mumtaz Digital** category should appear under Blocks.
5. Set the intended website for the page in Website pages/settings if this database hosts multiple websites; the package does not pick a `website_id` automatically. Keep it unpublished until that ownership is verified.
6. Use Website's native menu editor to link the page and select it as homepage **only after review and approval**.
7. Test the form with a synthetic enquiry, confirm it creates a CRM opportunity/lead, configure reCAPTCHA/Turnstile or other anti-abuse controls, and verify email notifications/consent/privacy messages.

## Important notes

- Because the page record is `noupdate=1`, edits made in Odoo Website Builder won't be overwritten by routine module updates. Updating the **source snippets** changes future blocks inserted from the library, but not previously edited copies. Plan content migrations explicitly.
- Edit logo, header and menu using Odoo's standard Website editor. This module deliberately does not take over those global elements.
- Product statistics and ZAKI replies are **illustrative demo content**, not live business data; update these before public publication.
- The Jawhar illustration was reused from the prior Mumtaz design concept. It is editable via the Website Builder image tools.
- No actual SaaS tenant provisioning, AI execution or fintech integration is implemented by this marketing addon.
- `Space Grotesk` and `Inter` are requested from Google Fonts through the v1 `css?family=` URL (the `css2` form contains `;` and is cut by Odoo's bundler, which invalidates the whole frontend stylesheet). For bank-controlled/data-residency scenarios, replace those with appropriately licensed, approved locally hosted fonts and update the CSS. No font binaries are bundled.
- Public form implementation follows Odoo's standard Website Form (requires `website_crm`), narrowed by a small controller override for this one form (required fields, e-mail format, honeypot). Installed and tested on a fresh Odoo 19 Community database on 21 Nov 2026: see `docs/mumtaz-website/README.md` for the test record, the issues corrected and the production checklist.

## Verification checklist

- [ ] Install on clean Odoo 19 Community staging instance.
- [ ] Confirm no existing homepage, menus or unrelated websites are affected.
- [ ] Verify all 7 building blocks appear in the editor and can be dragged and reordered.
- [ ] Change heading, text, button links and Jawhar image through Odoo Website editor; save, reload, verify persistence.
- [ ] Check desktop, tablet and mobile rendering within the actual Odoo theme/header/footer.
- [ ] Submit synthetic CRM enquiry and verify routing.
- [ ] Configure site-specific header/footer menus, company branding and privacy notices.
- [ ] Verify accessibility (contrast, keyboard, focus), responsive performance and SEO metadata.
- [ ] Publish only after owner approval.

## Odoo documentation

- https://www.odoo.com/documentation/19.0/developer/howtos/website_themes/building_blocks.html
- https://www.odoo.com/documentation/19.0/developer/howtos/website_themes/pages.html
- https://www.odoo.com/documentation/19.0/applications/websites/website/web_design/building_blocks/forms.html
