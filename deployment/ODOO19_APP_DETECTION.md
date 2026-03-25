# Odoo 19 CE - Mumtaz app detection guide

If Odoo cannot detect `mumtaz_base`, `mumtaz_core`, `mumtaz_ai`, `mumtaz_cfo_base`, `mumtaz_cfo_ingestion`, `mumtaz_cfo_transactions`, or `mumtaz_cfo_toolkit`, the issue is usually `addons_path`/permissions/cache, not module code.

## 1) Find your database name
```bash
sudo -u postgres psql -lqt
```
Use the first column from your Odoo database row (example: `Mumtaz_ERP`).

## 2) Find where this repository exists on your server
```bash
find / -type f -name make_odoo_detect_mumtaz.sh 2>/dev/null
```
Example result:
`/opt/custom_addons/Mumtaz/deployment/make_odoo_detect_mumtaz.sh`

> If nothing is found, clone/pull this repository first.

## 3) Run the one-command fixer from the real path
```bash
sudo bash /opt/custom_addons/Mumtaz/deployment/make_odoo_detect_mumtaz.sh Mumtaz_ERP /etc/odoo/odoo.conf odoo
```

### Important shell note
- Do **not** type `<DB_NAME>` literally with angle brackets (`< >`).
- If you run commands from BusyBox `ash`, still invoke this helper with `bash` as shown above.

## 4) What the script does
- validates Mumtaz addon structure
- appends repository path to `addons_path` if missing
- fixes ownership/permissions
- restarts Odoo service
- refreshes app list (`-u base`)
- prints module detection state from `ir.module.module`

## 5) Manual fallback (if you prefer)
### Add repository to addons path
Edit your config:
- `/etc/odoo/odoo.conf` (or your service-specific config)

Set:
```ini
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/opt/odoo/custom_addons,/opt/custom_addons/Mumtaz
```

### Fix ownership/permissions
```bash
sudo chown -R odoo:odoo /opt/custom_addons/Mumtaz
sudo find /opt/custom_addons/Mumtaz -type d -exec chmod 755 {} \;
sudo find /opt/custom_addons/Mumtaz -type f -exec chmod 644 {} \;
```

### Restart Odoo
```bash
sudo systemctl restart odoo
sudo systemctl status odoo --no-pager
```

### Refresh app list
```bash
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d Mumtaz_ERP -u base --stop-after-init
```

### Verify modules exist in database
```bash
sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d Mumtaz_ERP <<'PY'
mods = env['ir.module.module'].search([('name', 'in', ['mumtaz_base','mumtaz_core','mumtaz_ai','mumtaz_cfo_base','mumtaz_cfo_ingestion','mumtaz_cfo_transactions','mumtaz_cfo_toolkit'])])
print(mods.mapped(lambda m: (m.name, m.state)))
PY
```

In UI: Apps -> clear filters -> search `Mumtaz`.

Tip: You can now install `mumtaz_cfo_toolkit` as a single compact module to install the full CFO stack in one step.

Tip: Installing `mumtaz_cfo_base` now auto-installs `mumtaz_cfo_ingestion` and `mumtaz_cfo_transactions` because they are configured with `auto_install` once dependencies are present.

## 6) If modules are installed but menus are not visible
- Ensure the user has **Mumtaz / CFO User** (or **Mumtaz / CFO Manager**) in Access Rights.
- CFO modules are now installable independently from `mumtaz_core`; they no longer rely on `mumtaz_core` group implications.
- Re-login after changing groups to refresh menu visibility.
