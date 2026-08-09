from . import controllers
from .favicon_setup import apply_favicon


def post_init_hook(env):
    """Replace Odoo's default favicon with the Faizy mark."""
    apply_favicon(env)
