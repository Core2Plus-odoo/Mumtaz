# config

`odoo.conf` is the Odoo configuration baked into the root `Dockerfile` and
mounted by the three root `docker-compose*.yml` files (local development and
the Compose-based staging/production definitions). It is **not** the
configuration of the Odoo services on the VPS, which read `/etc/odoo*.conf`.

Do not put secrets here. A local override, `config/odoo.conf.local`, is
git-ignored.
