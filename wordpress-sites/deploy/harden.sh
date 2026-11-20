#!/usr/bin/env bash
#
# Hardening + isolation pass for odditytrend.com and youngcraze.com.
#
# - Two dedicated PHP-FPM pools (8 workers each, 16 total) — isolates the
#   two sites from each other AND from whatever pool other sites on this
#   VPS (e.g. c2p-delivery-system) use. Each pool is also open_basedir-
#   restricted to its own site directory.
# - FastCGI page caching per site (separate cache zones, safe skip-cache
#   rules for admin/logged-in/POST/query-string requests).
# - XML-RPC disabled (403) — not used by these sites, common brute-force/
#   pingback-amplification target.
# - wp-login.php rate-limited to 5 requests/min/IP.
#
# Does NOT touch c2p-delivery-system or any other vhost on this VPS —
# only ever writes/replaces files for the two domains below.
#
# Existing Nginx configs are backed up before being regenerated, and SSL
# is re-attached via Certbot afterward (Certbot's own edits to these files
# would otherwise be wiped out by the regeneration).
#
# Usage: sudo bash harden.sh
set -euo pipefail

SITE1_DOMAIN="odditytrend.com"
SITE1_ROOT="/var/www/${SITE1_DOMAIN}"
SITE1_POOL="oddcraze-odditytrend"

SITE2_DOMAIN="youngcraze.com"
SITE2_ROOT="/var/www/${SITE2_DOMAIN}"
SITE2_POOL="oddcraze-youngcraze"

ADMIN_EMAIL="muhammad.umer@logitive.de"

log()  { echo -e "\n\033[1;34m▶ $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $*\033[0m"; }
die()  { echo -e "\033[1;31m✖ $*\033[0m"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run this as root (sudo bash harden.sh)."

PHP_VER="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
PHP_FPM_DIR="/etc/php/${PHP_VER}/fpm"
[ -d "$PHP_FPM_DIR" ] || die "Could not find PHP-FPM config dir at ${PHP_FPM_DIR} — check the PHP version on this box."

# ─────────────────────────────────────────────────────────────────────────
log "Step 1/4 — Dedicated PHP-FPM pools (8 workers each, 16 total)"
# ─────────────────────────────────────────────────────────────────────────
write_pool() {
	local name="$1" root="$2"
	cat > "${PHP_FPM_DIR}/pool.d/${name}.conf" <<-POOL
		[${name}]
		user = www-data
		group = www-data
		listen = /run/php/${name}.sock
		listen.owner = www-data
		listen.group = www-data
		pm = dynamic
		pm.max_children = 8
		pm.start_servers = 2
		pm.min_spare_servers = 1
		pm.max_spare_servers = 4
		php_admin_value[open_basedir] = ${root}:/tmp
	POOL
}

write_pool "$SITE1_POOL" "$SITE1_ROOT"
write_pool "$SITE2_POOL" "$SITE2_ROOT"

"php-fpm${PHP_VER}" -t
PHP_FPM_SERVICE="$(systemctl list-units --type=service --all --no-legend 2>/dev/null | awk '{print $1}' | grep -m1 -E '^php[0-9.]*-fpm\.service$')"
[ -n "$PHP_FPM_SERVICE" ] || die "Could not find the php-fpm systemd service name."
systemctl reload "$PHP_FPM_SERVICE"

echo "  ${SITE1_POOL} (8 workers, open_basedir=${SITE1_ROOT}) and ${SITE2_POOL} (8 workers, open_basedir=${SITE2_ROOT}) are live."
echo "  Note: open_basedir restricts each pool to its own site dir + /tmp — watch for a rare plugin needing a path outside that, and widen it if so."

# ─────────────────────────────────────────────────────────────────────────
log "Step 2/4 — FastCGI cache zones + login rate-limit zone (additive, shared nginx.conf includes)"
# ─────────────────────────────────────────────────────────────────────────
mkdir -p /var/cache/nginx/odditytrend /var/cache/nginx/youngcraze
chown -R www-data:www-data /var/cache/nginx

cat > /etc/nginx/conf.d/oddcraze-cache.conf <<-'NGINX'
	fastcgi_cache_path /var/cache/nginx/odditytrend levels=1:2 keys_zone=ODDITYCACHE:50m inactive=60m max_size=512m;
	fastcgi_cache_path /var/cache/nginx/youngcraze levels=1:2 keys_zone=YOUNGCACHE:50m inactive=60m max_size=512m;
	fastcgi_cache_key "$scheme$request_method$host$request_uri";
	limit_req_zone $binary_remote_addr zone=wplogin_limit:10m rate=5r/m;
NGINX
# This file only defines zones — it has no effect on any other vhost's
# server blocks unless they explicitly reference these zone names, which
# none of them do.

# ─────────────────────────────────────────────────────────────────────────
log "Step 3/4 — Regenerating site Nginx configs (backed up first)"
# ─────────────────────────────────────────────────────────────────────────
BACKUP_DIR="/root/nginx-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp "/etc/nginx/sites-available/${SITE1_DOMAIN}" "${BACKUP_DIR}/" 2>/dev/null || true
cp "/etc/nginx/sites-available/${SITE2_DOMAIN}" "${BACKUP_DIR}/" 2>/dev/null || true
echo "  Backed up to ${BACKUP_DIR}"

write_hardened_block() {
	local domain="$1" root="$2" pool="$3" cache_zone="$4"
	local conf="/etc/nginx/sites-available/${domain}"

	cat > "$conf" <<-NGINX
		server {
		    listen 80;
		    listen [::]:80;
		    server_name ${domain} www.${domain};

		    root ${root};
		    index index.php;

		    client_max_body_size 64M;

		    access_log /var/log/nginx/${domain}.access.log;
		    error_log  /var/log/nginx/${domain}.error.log;

		    location = /xmlrpc.php {
		        deny all;
		        return 403;
		    }

		    location = /wp-login.php {
		        limit_req zone=wplogin_limit burst=3 nodelay;
		        include snippets/fastcgi-php.conf;
		        fastcgi_pass unix:/run/php/${pool}.sock;
		    }

		    location / {
		        try_files \$uri \$uri/ /index.php?\$args;
		    }

		    set \$skip_cache 0;
		    if (\$request_method = POST) { set \$skip_cache 1; }
		    if (\$query_string != "") { set \$skip_cache 1; }
		    if (\$request_uri ~* "/wp-admin/|/xmlrpc.php|wp-.*\.php|/feed/") { set \$skip_cache 1; }
		    if (\$http_cookie ~* "comment_author|wordpress_[a-f0-9]+|wp-postpass|wordpress_no_cache|wordpress_logged_in") { set \$skip_cache 1; }

		    location ~ \.php\$ {
		        include snippets/fastcgi-php.conf;
		        fastcgi_pass unix:/run/php/${pool}.sock;
		        fastcgi_cache ${cache_zone};
		        fastcgi_cache_valid 200 60m;
		        fastcgi_cache_bypass \$skip_cache;
		        fastcgi_no_cache \$skip_cache;
		        add_header X-FastCGI-Cache \$upstream_cache_status;
		    }

		    location ~ /\.ht {
		        deny all;
		    }

		    location = /favicon.ico { log_not_found off; access_log off; }
		    location = /robots.txt  { log_not_found off; access_log off; allow all; }
		}
	NGINX

	ln -sf "$conf" "/etc/nginx/sites-enabled/${domain}"
}

write_hardened_block "$SITE1_DOMAIN" "$SITE1_ROOT" "$SITE1_POOL" "ODDITYCACHE"
write_hardened_block "$SITE2_DOMAIN" "$SITE2_ROOT" "$SITE2_POOL" "YOUNGCACHE"

nginx -t
systemctl reload nginx

# ─────────────────────────────────────────────────────────────────────────
log "Step 4/4 — Re-attaching SSL via Certbot (idempotent, reuses existing certs)"
# ─────────────────────────────────────────────────────────────────────────
certbot --nginx -d "$SITE1_DOMAIN" -d "www.${SITE1_DOMAIN}" --non-interactive --agree-tos --redirect -m "$ADMIN_EMAIL" \
	|| warn "Certbot re-attach failed for ${SITE1_DOMAIN} — HTTPS may be down. Restore from ${BACKUP_DIR} if so (see summary below)."
certbot --nginx -d "$SITE2_DOMAIN" -d "www.${SITE2_DOMAIN}" --non-interactive --agree-tos --redirect -m "$ADMIN_EMAIL" \
	|| warn "Certbot re-attach failed for ${SITE2_DOMAIN} — HTTPS may be down. Restore from ${BACKUP_DIR} if so (see summary below)."

nginx -t
systemctl reload nginx

echo
echo "=== Verifying both sites ==="
for domain in "$SITE1_DOMAIN" "$SITE2_DOMAIN"; do
	code=$(curl -sk -o /dev/null -w '%{http_code}' "https://${domain}/")
	echo "  https://${domain}/ → HTTP ${code}"
done

cat <<-DONE

	Done.

	If either site above did NOT return 200, roll back immediately:
	  cp ${BACKUP_DIR}/${SITE1_DOMAIN} /etc/nginx/sites-available/${SITE1_DOMAIN}
	  cp ${BACKUP_DIR}/${SITE2_DOMAIN} /etc/nginx/sites-available/${SITE2_DOMAIN}
	  nginx -t && systemctl reload nginx

	To confirm caching is working once the site has some traffic:
	  curl -sI https://${SITE1_DOMAIN}/ | grep -i x-fastcgi-cache
	(first hit = MISS, subsequent hits within 60min = HIT)
DONE
