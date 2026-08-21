# Oddity Trend — WordPress theme

Custom lightweight theme for **odditytrend.com** (weird news / strange facts).
Built from scratch — no page builder, no bundled framework, no build step.
Plain PHP + one CSS file + one small JS file.

## Install

1. Zip this directory (or copy it) into `wp-content/themes/odditytrend-theme/`
   on the server.
2. Activate it under **Appearance → Themes**.
3. Set a custom logo and site tagline under **Appearance → Customize → Site
   Identity** (tagline shows as the small caps line under the logo).
4. Create a **Primary Menu** and a **Footer Menu** under **Appearance →
   Menus**, and assign them to the "Primary Menu" / "Footer Menu" locations.
5. Set **Settings → Reading → Homepage displays** to "A static page" is *not*
   required — `front-page.php` already renders the featured-story + latest
   grid homepage automatically from your posts.

## Ad slots (AdSense-ready, no code edits needed)

Go to **Appearance → Customize → Ad Slots**. Four textarea fields —
`Header`, `In-article`, `Sidebar`, `Footer` — accept raw AdSense (or any ad
network) `<script>`/`<ins>` snippets and are output as-is in the matching
template location. Leave a field empty and that slot renders nothing (no
empty containers, no layout shift).

These fields are gated to users capable of `unfiltered_html` (admins), the
same trust level WordPress already grants for raw theme customization.

## Structure

- `style.css` — theme header + all CSS (design tokens as CSS custom
  properties at the top).
- `functions.php` — theme supports, menus, image sizes, widget area,
  ad-slot helper (`ot_ad_slot()`).
- `header.php` / `footer.php` — site chrome.
- `front-page.php` — homepage (featured story + latest grid).
- `index.php` — fallback blog listing.
- `single.php` / `page.php` — post/page templates.
- `archive.php` / `search.php` / `404.php` — remaining template hierarchy.
- `template-parts/` — reusable post card / single article / empty-state
  partials.
- `inc/template-tags.php` — small helper functions (byline, pagination).
- `inc/customizer.php` — the ad-slot Customizer section.
- `assets/js/main.js` — mobile menu toggle only, no other JS.

## Not included

- `screenshot.png` (1200×900) for the theme switcher grid — add one before
  distributing the theme, purely cosmetic, not required to run.
- Any AdSense/Rank Math/caching plugin config — installed separately via
  wp-admin per the project plan.
