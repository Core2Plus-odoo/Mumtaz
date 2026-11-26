"""19.0.1.4.0: checklists on the FAIZY activity types (§25).

The types are noupdate data (Umer tunes the escalation windows), so an
upgrade does not touch them; this fills the Default Note where it is still
empty and leaves an edited note alone.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['faizy.routing']._apply_checklists()
