def post_init_hook(env):
    """First install: put the checklists on the FAIZY activity types."""
    env['faizy.routing']._apply_checklists()
