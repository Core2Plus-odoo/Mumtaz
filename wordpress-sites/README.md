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

`deploy/setup-lemp.sh` provisions both sites end-to-end on the shared
Hostinger VPS: installs Nginx + MariaDB + PHP-FPM, creates two isolated
databases (one per site, so odditytrend and youngcraze can never read each
other's data), installs WordPress core, deploys both themes from this repo,
adds Nginx server blocks, opens the firewall, and issues Let's Encrypt
certificates. It's safe to re-run (every step checks current state first)
and never touches the existing c2p-delivery-system Nginx config on the same
box.

Run it as root on the VPS, after DNS for both domains already points at the
VPS IP (the script checks this first and aborts if it doesn't):

```bash
sudo bash deploy/setup-lemp.sh
```

It deliberately stops short of the WordPress install wizard — visit
`https://<domain>/wp-admin/install.php` yourself afterward to set each
site's title and admin account, then activate the matching theme under
**Appearance → Themes**. See the per-theme `README.md` for menu setup and
ad slot configuration.

Publishing plugins (Rank Math, a caching plugin) and content are handled
separately via wp-admin, per the project plan.
