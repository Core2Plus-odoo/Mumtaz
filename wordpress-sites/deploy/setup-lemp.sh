#!/usr/bin/env bash
#
# LEMP setup for odditytrend.com and youngcraze.com on the shared Hostinger VPS.
#
# Installs Nginx + MariaDB + PHP-FPM, creates two isolated databases (one per
# site), installs WordPress core for each, deploys the custom themes from
# this repo, adds Nginx server blocks, opens the firewall, and issues
# Let's Encrypt certificates.
#
# Safe to re-run: every step checks current state before acting. Does NOT
# touch any existing site config on this VPS (e.g. the c2p-delivery-system /
# delivery.mumtaz.digital Nginx config) — it only adds new files under
# sites-available/sites-enabled for the two domains below, and reloads
# (never restarts) Nginx after validating the config with `nginx -t`.
#
# Does NOT run the WordPress browser install wizard and does NOT set an
# admin username/password — that step is manual, by design.
#
# Credentials are read from environment variables — NOT hardcoded here, so
# this script is safe to commit to git. Set them before running, e.g.:
#
#   set -a; source ./setup-lemp.env; set +a; sudo -E bash setup-lemp.sh
#
# Required: ADMIN_EMAIL, MYSQL_ROOT_PASS, DB1_PASS, DB2_PASS
# (setup-lemp.env is gitignored — see setup-lemp.env.example for the format)
#
# Usage: sudo -E bash setup-lemp.sh
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────
: "${ADMIN_EMAIL:?Set ADMIN_EMAIL (SSL certificate + WP admin email) in the environment before running}"
: "${MYSQL_ROOT_PASS:?Set MYSQL_ROOT_PASS in the environment before running}"
: "${DB1_PASS:?Set DB1_PASS (odditytrend DB password) in the environment before running}"
: "${DB2_PASS:?Set DB2_PASS (youngcraze DB password) in the environment before running}"

VPS_IP="187.77.128.199"

SITE1_DOMAIN="odditytrend.com"
SITE1_ROOT="/var/www/${SITE1_DOMAIN}"
SITE1_TITLE="OddityTrend"
DB1_NAME="odditytrend_wp"
DB1_USER="odditytrend_wpuser"
SITE1_THEME="odditytrend-theme"

SITE2_DOMAIN="youngcraze.com"
SITE2_ROOT="/var/www/${SITE2_DOMAIN}"
SITE2_TITLE="YoungCraze"
DB2_NAME="youngcraze_wp"
DB2_USER="youngcraze_wpuser"
SITE2_THEME="youngcraze-theme"

REPO_URL="https://github.com/Core2Plus-odoo/Mumtaz.git"
REPO_BRANCH="main"   # use claude/new-session-nyxfo8 if PR #132 hasn't merged yet

# ─────────────────────────────────────────────────────────────────────────
log()  { echo -e "\n\033[1;34m▶ $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $*\033[0m"; }
die()  { echo -e "\033[1;31m✖ $*\033[0m"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run this as root (sudo -E bash setup-lemp.sh)."

# ─────────────────────────────────────────────────────────────────────────
log "Step 0/10 — Checking DNS propagation before doing anything else"
# ─────────────────────────────────────────────────────────────────────────
command -v dig >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq dnsutils; }

check_dns() {
	local host="$1" resolved
	resolved="$(dig +short "$host" | tail -n1)"
	if [ "$resolved" != "$VPS_IP" ]; then
		warn "$host resolves to '${resolved:-<nothing>}', expected $VPS_IP"
		return 1
	fi
	echo "  ✓ $host → $resolved"
	return 0
}

dns_ok=1
for h in "$SITE1_DOMAIN" "www.$SITE1_DOMAIN" "$SITE2_DOMAIN" "www.$SITE2_DOMAIN"; do
	check_dns "$h" || dns_ok=0
done
[ "$dns_ok" -eq 1 ] || die "DNS not fully propagated yet. Re-run once all four hostnames above resolve to $VPS_IP (Certbot will fail otherwise)."

# ─────────────────────────────────────────────────────────────────────────
log "Step 1/10 — System update"
# ─────────────────────────────────────────────────────────────────────────
apt-get update -qq
apt-get upgrade -y -qq

# ─────────────────────────────────────────────────────────────────────────
log "Step 2/10 — Installing Nginx, MariaDB, PHP-FPM + extensions"
# ─────────────────────────────────────────────────────────────────────────
# NOTE: this VPS already runs Nginx for the existing c2p-delivery-system
# site. Installing the nginx package again is a no-op if present and does
# NOT remove or alter existing sites-available/sites-enabled files.
apt-get install -y -qq \
	nginx mariadb-server \
	php-fpm php-mysql php-xml php-curl php-gd php-mbstring php-zip php-intl php-imagick \
	unzip curl git rsync ufw

PHP_FPM_SOCK="$(find /run/php -maxdepth 1 -name 'php*-fpm.sock' 2>/dev/null | sort -V | tail -n1)"
[ -n "$PHP_FPM_SOCK" ] || die "Could not detect a php-fpm socket under /run/php — check the PHP-FPM package name for this OS release and adjust manually."
log "Detected PHP-FPM socket: $PHP_FPM_SOCK"

# ─────────────────────────────────────────────────────────────────────────
log "Step 3/10 — Securing MariaDB (equivalent of mysql_secure_installation)"
# ─────────────────────────────────────────────────────────────────────────
# Fresh MariaDB installs on Debian/Ubuntu default root to unix_socket auth,
# so `mysql` run as root works with no password yet. Detect which auth mode
# is currently live so this is safe to re-run after the password is set.
if mysql -u root -e "SELECT 1;" >/dev/null 2>&1; then
	MYSQL_ROOT_CMD=(mysql -u root)
elif mysql -u root -p"${MYSQL_ROOT_PASS}" -e "SELECT 1;" >/dev/null 2>&1; then
	MYSQL_ROOT_CMD=(mysql -u root -p"${MYSQL_ROOT_PASS}")
else
	die "Could not authenticate to MariaDB as root (neither socket auth nor MYSQL_ROOT_PASS worked) — check the install manually."
fi

"${MYSQL_ROOT_CMD[@]}" -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASS}'; FLUSH PRIVILEGES;"
mysql -u root -p"${MYSQL_ROOT_PASS}" -e "DROP DATABASE IF EXISTS test;"
mysql -u root -p"${MYSQL_ROOT_PASS}" -e "DELETE FROM mysql.user WHERE User='';" 2>/dev/null \
	|| warn "Could not clean up anonymous MySQL users (table layout differs on this MariaDB version) — not critical, continuing."
mysql -u root -p"${MYSQL_ROOT_PASS}" -e "FLUSH PRIVILEGES;"

# ─────────────────────────────────────────────────────────────────────────
log "Step 4/10 — Creating two isolated databases + users (one per site)"
# ─────────────────────────────────────────────────────────────────────────
mysql -u root -p"${MYSQL_ROOT_PASS}" <<-SQL
	CREATE DATABASE IF NOT EXISTS ${DB1_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
	CREATE USER IF NOT EXISTS '${DB1_USER}'@'localhost' IDENTIFIED BY '${DB1_PASS}';
	GRANT ALL PRIVILEGES ON ${DB1_NAME}.* TO '${DB1_USER}'@'localhost';

	CREATE DATABASE IF NOT EXISTS ${DB2_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
	CREATE USER IF NOT EXISTS '${DB2_USER}'@'localhost' IDENTIFIED BY '${DB2_PASS}';
	GRANT ALL PRIVILEGES ON ${DB2_NAME}.* TO '${DB2_USER}'@'localhost';

	FLUSH PRIVILEGES;
SQL
# Each user is scoped to its own database only — odditytrend_wpuser cannot
# read/write youngcraze_wp, and neither can touch the c2p-delivery-system's
# own storage (which is SQLite, not MariaDB, so there's no overlap at all).

# ─────────────────────────────────────────────────────────────────────────
log "Step 5/10 — Installing WP-CLI"
# ─────────────────────────────────────────────────────────────────────────
if ! command -v wp >/dev/null 2>&1; then
	curl -sS -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
	chmod +x /usr/local/bin/wp
fi
wp --version --allow-root

# ─────────────────────────────────────────────────────────────────────────
log "Step 6/10 — Fetching theme source from the repo"
# ─────────────────────────────────────────────────────────────────────────
THEMES_TMP="$(mktemp -d)"
git clone --depth 1 --branch "$REPO_BRANCH" --filter=blob:none --sparse "$REPO_URL" "$THEMES_TMP/repo"
git -C "$THEMES_TMP/repo" sparse-checkout set wordpress-sites

setup_site() {
	local domain="$1" root="$2" title="$3" db_name="$4" db_user="$5" db_pass="$6" theme="$7"

	log "Setting up ${domain}"

	mkdir -p "$root"
	if [ ! -f "$root/wp-load.php" ]; then
		wp core download --path="$root" --allow-root
	else
		echo "  WordPress core already present, skipping download."
	fi

	if [ ! -f "$root/wp-config.php" ]; then
		wp config create \
			--path="$root" \
			--dbname="$db_name" \
			--dbuser="$db_user" \
			--dbpass="$db_pass" \
			--dbhost="localhost" \
			--allow-root
	else
		echo "  wp-config.php already present, skipping."
	fi

	mkdir -p "$root/wp-content/themes"
	rsync -a --delete "$THEMES_TMP/repo/wordpress-sites/${theme}/" "$root/wp-content/themes/${theme}/"

	chown -R www-data:www-data "$root"
	find "$root" -type d -exec chmod 755 {} \;
	find "$root" -type f -exec chmod 644 {} \;

	echo "  ${title} is staged at ${root} — WordPress core installed, DB configured, theme deployed."
	echo "  NOT running the install wizard — visit https://${domain}/wp-admin/install.php yourself to set the site title/admin account."
}

setup_site "$SITE1_DOMAIN" "$SITE1_ROOT" "$SITE1_TITLE" "$DB1_NAME" "$DB1_USER" "$DB1_PASS" "$SITE1_THEME"
setup_site "$SITE2_DOMAIN" "$SITE2_ROOT" "$SITE2_TITLE" "$DB2_NAME" "$DB2_USER" "$DB2_PASS" "$SITE2_THEME"

rm -rf "$THEMES_TMP"

# ─────────────────────────────────────────────────────────────────────────
log "Step 7/10 — Nginx server blocks"
# ─────────────────────────────────────────────────────────────────────────
write_server_block() {
	local domain="$1" root="$2"
	local conf="/etc/nginx/sites-available/${domain}"

	cat > "$conf" <<-NGINX
		server {
		    listen 80;
		    listen [::]:80;
		    server_name ${domain} www.${domain};

		    root ${root};
		    index index.php;

		    access_log /var/log/nginx/${domain}.access.log;
		    error_log  /var/log/nginx/${domain}.error.log;

		    location / {
		        try_files \$uri \$uri/ /index.php?\$args;
		    }

		    location ~ \.php\$ {
		        include snippets/fastcgi-php.conf;
		        fastcgi_pass unix:${PHP_FPM_SOCK};
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

write_server_block "$SITE1_DOMAIN" "$SITE1_ROOT"
write_server_block "$SITE2_DOMAIN" "$SITE2_ROOT"

nginx -t
systemctl reload nginx

# ─────────────────────────────────────────────────────────────────────────
log "Step 8/10 — Firewall (ufw)"
# ─────────────────────────────────────────────────────────────────────────
# Additive only — does not reset or remove any existing rules on this
# shared VPS.
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
if ufw status | grep -q "Status: inactive"; then
	ufw --force enable
else
	echo "  ufw already active — rules added, nothing else changed."
fi

# ─────────────────────────────────────────────────────────────────────────
log "Step 9/10 — Let's Encrypt SSL via Certbot"
# ─────────────────────────────────────────────────────────────────────────
apt-get install -y -qq certbot python3-certbot-nginx

certbot_for() {
	local domain="$1"
	certbot --nginx \
		-d "$domain" -d "www.${domain}" \
		--non-interactive --agree-tos --redirect \
		-m "$ADMIN_EMAIL" \
		|| warn "Certbot failed for ${domain} — likely DNS not fully propagated yet. Retry manually once it is:\n    certbot --nginx -d ${SITE1_DOMAIN} -d www.${SITE1_DOMAIN} -d ${SITE2_DOMAIN} -d www.${SITE2_DOMAIN}"
}

certbot_for "$SITE1_DOMAIN"
certbot_for "$SITE2_DOMAIN"

# ─────────────────────────────────────────────────────────────────────────
log "Step 10/10 — Verifying both sites are reachable"
# ─────────────────────────────────────────────────────────────────────────
for domain in "$SITE1_DOMAIN" "$SITE2_DOMAIN"; do
	code="$(curl -s -o /dev/null -w '%{http_code}' "https://${domain}/wp-admin/install.php" || echo "curl-failed")"
	echo "  https://${domain}/wp-admin/install.php → HTTP ${code}"
done

cat <<-DONE

	Done.

	Next (manual, by design):
	  1. Visit https://${SITE1_DOMAIN}/wp-admin/install.php and https://${SITE2_DOMAIN}/wp-admin/install.php
	     to set each site's title and admin account.
	  2. Activate the "${SITE1_TITLE}" / "${SITE2_TITLE}" theme under Appearance → Themes on each site.
	  3. Move the DB/root passwords in this script into a password manager, then delete this file
	     from the server: rm $(readlink -f "$0" 2>/dev/null || echo "<this-script-path>")
DONE
