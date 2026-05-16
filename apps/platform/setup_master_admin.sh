#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Mumtaz Platform — Master Admin Setup
#
# Makes umer@mumtaz.digital the platform super admin in ALL systems:
#   1. Portal / Auth (SQLite at /opt/zaki-server/users.db)
#      - Creates user if not exists
#      - Sets MUMTAZ_ADMINS to include umer@mumtaz.digital
#   2. ERP (PostgreSQL mumtaz_erp)
#      - Creates or promotes umer@mumtaz.digital to is_super_admin=TRUE
#
# Usage:
#   cd /opt/Mumtaz
#   sudo bash apps/platform/setup_master_admin.sh
#
# Options:
#   ADMIN_EMAIL=other@example.com sudo bash ... — use a different email
#   ADMIN_PASS=mypass sudo bash ...             — set a specific password
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ADMIN_EMAIL="${ADMIN_EMAIL:-umer@mumtaz.digital}"
PORTAL_DB="${PORTAL_DB:-/opt/zaki-server/users.db}"
ERP_DB_NAME="${ERP_DB_NAME:-mumtaz_erp}"
ERP_DB_USER="${ERP_DB_USER:-erp_user}"

# ── Password ──────────────────────────────────────────────────────────────────
if [ -z "${ADMIN_PASS:-}" ]; then
  echo ""
  read -rsp "Enter password for ${ADMIN_EMAIL}: " ADMIN_PASS
  echo ""
  read -rsp "Confirm password: " ADMIN_PASS2
  echo ""
  if [ "$ADMIN_PASS" != "$ADMIN_PASS2" ]; then
    echo "❌  Passwords do not match."; exit 1
  fi
  if [ "${#ADMIN_PASS}" -lt 8 ]; then
    echo "❌  Password must be at least 8 characters."; exit 1
  fi
fi

# ── Hash the password (bcrypt via Python) ─────────────────────────────────────
PYTHON_BIN=$(command -v python3 || command -v python)
VENV_PYTHON="/opt/zaki-server/venv/bin/python3"
[ -x "$VENV_PYTHON" ] && PYTHON_BIN="$VENV_PYTHON"

PHASH=$("$PYTHON_BIN" -c "
import bcrypt, sys
pw = sys.argv[1].encode()
print(bcrypt.hashpw(pw, bcrypt.gensalt()).decode())
" "$ADMIN_PASS")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Mumtaz Master Admin Setup"
echo " Email : ${ADMIN_EMAIL}"
echo " Portal: ${PORTAL_DB}"
echo " ERP DB: ${ERP_DB_NAME}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Portal SQLite ──────────────────────────────────────────────────────────
echo ""
echo "→ [1/3] Updating Portal database…"

if [ ! -f "$PORTAL_DB" ]; then
  echo "  ⚠️  Portal DB not found at $PORTAL_DB — skipping portal setup."
else
  "$PYTHON_BIN" - "$PORTAL_DB" "$ADMIN_EMAIL" "$PHASH" <<'PYEOF'
import sqlite3, sys

db_path, email, phash = sys.argv[1], sys.argv[2], sys.argv[3]
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Ensure erp_company_id column exists
try:
    conn.execute("ALTER TABLE users ADD COLUMN erp_company_id INTEGER")
except Exception:
    pass

existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
if existing:
    conn.execute(
        "UPDATE users SET password_hash=?, active=1, role='admin' WHERE email=?",
        (phash, email)
    )
    print(f"  ✅ Updated existing user: {email}")
else:
    conn.execute(
        "INSERT INTO users (email, password_hash, name, plan, active, role) "
        "VALUES (?, ?, 'Platform Admin', 'scale', 1, 'admin')",
        (email, phash)
    )
    print(f"  ✅ Created portal user: {email}")

# Update MUMTAZ_ADMINS in settings table
conn.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at INTEGER DEFAULT (strftime('%s','now')),
        updated_by TEXT
    )
""")
row = conn.execute("SELECT value FROM settings WHERE key='MUMTAZ_ADMINS'").fetchone()
current = (row["value"] or "") if row else ""
existing_admins = {e.strip().lower() for e in current.split(",") if e.strip()}
existing_admins.add(email.lower())
new_val = ",".join(sorted(existing_admins))
conn.execute(
    "INSERT INTO settings (key, value, updated_by) VALUES ('MUMTAZ_ADMINS', ?, 'setup_script') "
    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=strftime('%s','now'), updated_by=excluded.updated_by",
    (new_val,)
)
print(f"  ✅ MUMTAZ_ADMINS = {new_val}")

conn.commit()
conn.close()
PYEOF
fi

# ── 2. ERP PostgreSQL ─────────────────────────────────────────────────────────
echo ""
echo "→ [2/3] Updating ERP database…"

ERP_PYTHON="/opt/erp-server/venv/bin/python3"
[ ! -x "$ERP_PYTHON" ] && ERP_PYTHON="$PYTHON_BIN"

"$ERP_PYTHON" - "$ADMIN_EMAIL" "$PHASH" "$ERP_DB_NAME" "$ERP_DB_USER" <<'PYEOF'
import sys
try:
    import psycopg2, psycopg2.extras
except ImportError:
    print("  ⚠️  psycopg2 not available — skipping ERP setup.")
    sys.exit(0)

email, phash, db_name, db_user = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

try:
    conn = psycopg2.connect(
        dbname=db_name, user=db_user, password="erp_secure_pass_change_me", host="localhost"
    )
except Exception as e:
    # Try with env password
    import os
    db_url = os.environ.get("ERP_DATABASE_URL", "")
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        print(f"  ⚠️  Cannot connect to ERP DB: {e} — skipping ERP setup.")
        sys.exit(0)

conn.autocommit = False
c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Ensure column exists
try:
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT FALSE")
    conn.commit()
except Exception:
    conn.rollback()

# Check if user already exists
c.execute("SELECT id, is_super_admin FROM users WHERE email=%s", (email,))
row = c.fetchone()
if row:
    c.execute(
        "UPDATE users SET password_hash=%s, is_super_admin=TRUE, active=TRUE, role='admin' WHERE email=%s",
        (phash, email)
    )
    print(f"  ✅ Promoted existing ERP user to super admin: {email}")
else:
    # Check if any super admin already exists
    c.execute("SELECT id FROM users WHERE is_super_admin=TRUE LIMIT 1")
    has_super = c.fetchone()
    if has_super:
        print(f"  ℹ️  A super admin already exists. Adding {email} as additional super admin.")
    c.execute(
        "INSERT INTO users (name, email, password_hash, role, is_super_admin, company_id) "
        "VALUES ('Platform Admin', %s, %s, 'admin', TRUE, NULL)",
        (email, phash)
    )
    print(f"  ✅ Created ERP super admin: {email}")

conn.commit()
conn.close()
PYEOF

# ── 3. Restart services ───────────────────────────────────────────────────────
echo ""
echo "→ [3/3] Restarting services to pick up new admin config…"

if systemctl is-active --quiet zaki-server 2>/dev/null; then
  systemctl restart zaki-server
  echo "  ✅ zaki-server restarted"
fi

if systemctl is-active --quiet erp-server 2>/dev/null; then
  systemctl restart erp-server
  echo "  ✅ erp-server restarted"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅  Master admin setup complete!"
echo ""
echo "   Portal admin:  https://app.mumtaz.digital/admin.html"
echo "   ERP admin:     https://erp.mumtaz.digital"
echo ""
echo "   Login email:   ${ADMIN_EMAIL}"
echo "   Password:      (the one you entered)"
echo ""
echo "   From the portal admin panel you can:"
echo "   • Manage all customer accounts and billing plans"
echo "   • Promote other users to admin (Make Admin button)"
echo "   • Sync portal users → ERP tenants (⚡ Sync All button)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
