"""Put "Our AI team" under About Us on the live site and keep the Get started button last.

See faizy_website/menu_setup.py for why the entry was detached. The data file
is noupdate, so a running database needs this step.
"""

import importlib.util
import os

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    path = os.path.join(os.path.dirname(__file__), "..", "..", "menu_setup.py")
    spec = importlib.util.spec_from_file_location("faizy_website_menu_setup", os.path.abspath(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.fix_header_menu(api.Environment(cr, SUPERUSER_ID, {}))
