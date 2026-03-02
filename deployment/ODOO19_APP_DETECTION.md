# Odoo 19 CE - Mumtaz app detection guide

If Odoo cannot detect `mumtaz_base`, `mumtaz_core`, or `mumtaz_ai`, the issue is usually `addons_path`/permissions/cache, not module code.

## 1) Put this repository in Odoo addons path
For Ubuntu package installs, edit:

- `/etc/odoo/odoo.conf` (or your service-specific config)

Set:

```ini
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/opt/odoo/custom_addons,/workspace/Mumtaz
```

> Keep your default path and append this repository path.

## 2) Fix ownership/permissions
```bash
sudo chown -R odoo:odoo /workspace/Mumtaz
sudo find /workspace/Mumtaz -type d -exec chmod 755 {} \;
sudo find /workspace/Mumtaz -type f -exec chmod 644 {} \;
```

## 3) Restart Odoo service
```bash
sudo systemctl restart odoo
sudo systemctl status odoo --no-pager
```

## 4) Update app list from CLI (recommended)
```bash
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d <DB_NAME> -u base --stop-after-init
```

## 5) Confirm modules are visible
```bash
sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d <DB_NAME> <<'PY'
env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
mods = env['ir.module.module'].search([('name', 'in', ['mumtaz_base','mumtaz_core','mumtaz_ai'])])
print(mods.mapped(lambda m: (m.name, m.state)))
PY
```

In UI: Apps -> clear filters -> search `Mumtaz`.
