from . import models


def post_init_hook(env):
    """Fresh install: seed every DEMO scenario. Upgrades re-seed through
    migrations/<version>/post-migrate.py (the hook only runs at install)."""
    env["pharma.demo.seed"].seed()
