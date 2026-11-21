# Jawhar — deployment runbook

All server actions are run by a named person after approval in the chat.
Production checkout `/opt/mumtaz` is never touched by Jawhar work.

## 1. Staging promotion (after a merge to `main`)

```bash
cd /opt/mumtaz-jewel-staging && git fetch origin main && git checkout -B jewel-staging origin/main && bash deploy/jewel-staging/deploy.sh --modules --upgrade --no-pull
```

`deploy.sh` installs/upgrades the module list (now including
`mumtaz_jewellery_website`), rsyncs `website/jewel` to
`/opt/mumtaz/jewel-landing`, builds the app, and runs `verify_site.sh`.

Top-up demo data when a slice adds seed records:

```bash
cd /opt/mumtaz-jewel-staging/deploy/jewel-staging && printf '%s\n' "from odoo.addons.mumtaz_jewellery_demo.hooks import top_up" "print(top_up(env)); env['jewellery.owner.card'].refresh(); env.cr.commit()" | docker compose -p mumtaz-jewel-staging run --rm --no-deps odoo odoo shell -c /etc/odoo/odoo.conf -d jewel_demo --no-http
```

## 2. nginx change required by this slice (needs approval)

The demo-request form posts to `/jawhar/public/site/demo-request`. On
staging every `/jawhar…` path is behind the demo password, so the form would
receive 401 and fall back to e-mail. The repository config
`deploy/jewel-staging/nginx/jewel.mumtaz.digital.conf` now carries a
`location ^~ /jawhar/public/site/` block without auth and a `limit_req`
zone (6 requests/minute per address). To apply:

```bash
cd /opt/mumtaz-jewel-staging && sudo bash deploy/jewel-staging/install_nginx_conf.sh && sudo nginx -t && sudo systemctl reload nginx
```

Then confirm from outside:

```bash
curl -s -X POST https://jewel.mumtaz.digital/jawhar/public/site/demo-request -H 'Content-Type: application/json' -d '{}' | head -c 200
```

Expected: a JSON `{"ok": false, "error": …}` with status 400, not a 401 and not HTML.

## 3. Rollback

Site: `git checkout <previous-sha> -- website/jewel` on the staging checkout and rerun the rsync step, or redeploy the previous `main`. Modules: `deploy.sh --upgrade` to the previous commit; the website module can stay installed (it adds tables only). nginx: `install_nginx_conf.sh` from the previous commit, `nginx -t`, reload.

## 4. Production (none yet)

Prerequisites: own host or isolated compose project with its own Postgres and volumes; secrets in the service env file only; backups with a restore drill; MFA for managers; monitoring; the control plane on its own database; DNS for the production domain; `noindex` removed only there. Each step needs a named approval; see `IMPLEMENTATION_ROADMAP.md` phase 10.

## 5. Guards

Never run `docker compose down -v` without confirming the project name and that containers exist; never copy `.env` between projects; never run deploy scripts from `/opt/mumtaz`.
