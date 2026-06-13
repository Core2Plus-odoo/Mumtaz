#!/usr/bin/env bash
# Restart any platform service that has fallen over. Run every 5 min via cron.
for svc in odoo zaki mumtaz-platform nginx postgresql; do
  systemctl is-active --quiet "$svc" || { systemctl restart "$svc"; echo "$(date) restarted $svc"; }
done
