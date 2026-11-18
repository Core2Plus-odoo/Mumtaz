from . import models


def post_init_hook(env):
    """Fresh install: seed the COD scenarios. Upgrades re-seed through migrations/<version>/post-migrate.py."""
    env["pharma.courier.demo.seed"].seed()
