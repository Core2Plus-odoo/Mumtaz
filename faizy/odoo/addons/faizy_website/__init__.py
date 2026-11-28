from . import controllers
from . import models
from .favicon_setup import apply_favicon
from .menu_setup import fix_header_menu


def post_init_hook(env):
    """Replace Odoo's default favicon with the Faizy mark and set the header menu right."""
    apply_favicon(env)
    fix_header_menu(env)
