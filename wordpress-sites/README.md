# WordPress sites

Two custom, from-scratch WordPress themes for AdSense content sites, built
for a manual LEMP deploy (Nginx + MariaDB + PHP-FPM) on the shared Hostinger
VPS — separate from the `c2p-delivery-system/` and `addons/` products in
this repo.

| Directory              | Domain            | Niche                                   |
|------------------------|-------------------|------------------------------------------|
| `odditytrend-theme/`   | odditytrend.com   | Weird news / strange facts               |
| `youngcraze-theme/`    | youngcraze.com    | Gen Z / internet trend explainers        |

Each theme is self-contained (its own `README.md` with install steps) —
plain PHP + one CSS file + one small vanilla-JS file, no page builder, no
build tooling, no bundled framework. Both ship with a Customizer-managed
**Ad Slots** panel (header / in-article / sidebar / footer) so AdSense code
can be pasted in from wp-admin once the site is live, with no template
edits required.

## Deploying

These are theme directories only — they assume WordPress core is already
installed (per the LEMP setup script covered separately). To go live:

1. Copy `odditytrend-theme/` to `/var/www/odditytrend.com/wp-content/themes/`
   and `youngcraze-theme/` to `/var/www/youngcraze.com/wp-content/themes/`.
2. Activate each theme under **Appearance → Themes** on its respective site.
3. Follow the per-theme `README.md` for menu setup and ad slot configuration.

Publishing plugins (Rank Math, a caching plugin) and content are handled
separately via wp-admin, per the project plan.
