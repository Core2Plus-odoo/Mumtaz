from . import models
from .accounting_setup import apply_accounting_profile
from .company_setup import apply_company_profile


def post_init_hook(env):
    """Set up the operating company on a fresh database.

    The two steps are independent on purpose. The accounting side has a long
    list of reasons to bail out — existing journal entries, a deliberately
    different country — and none of them are a reason to leave the company
    called "My Company" with no logo.
    """
    apply_accounting_profile(env)
    apply_company_profile(env)
