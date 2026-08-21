# Young Craze — WordPress theme

Custom lightweight theme for **youngcraze.com** (Gen Z / internet trend
explainers). Built from scratch — no page builder, no bundled framework, no
build step. Plain PHP + one CSS file + one small JS file.

## Install

1. Zip this directory (or copy it) into `wp-content/themes/youngcraze-theme/`
   on the server.
2. Activate it under **Appearance → Themes**.
3. Set a custom logo under **Appearance → Customize → Site Identity**.
4. Create a **Primary Menu** and a **Footer Menu** under **Appearance →
   Menus**, and assign them to the "Primary Menu" / "Footer Menu" locations.
5. The homepage (`front-page.php`) auto-renders a "🔥 Trending This Week"
   horizontal strip (your 5 most recent posts) followed by a "Latest
   Explainers" grid — no static page or manual configuration needed.

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
  properties at the top; purple/pink gradient identity, rounded cards).
- `functions.php` — theme supports, menus, image sizes, widget area,
  ad-slot helper (`yc_ad_slot()`).
- `header.php` / `footer.php` — site chrome (sticky header).
- `front-page.php` — homepage (trending strip + latest grid).
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
