from . import models

from .models.crm_stage import seed_proposal_stages


def post_init_hook(env):
    """Seed the proposal-stage flag from the pipeline that is already there.

    The follow-up agent selects on ``crm.stage.is_proposal_stage`` rather than
    matching stage names at runtime, because a stage rename should not silently
    switch an agent off. That trade is only worth making if the flag starts out
    correct, so it is seeded once here from the existing stage names and is a
    plain editable checkbox from then on.
    """
    seed_proposal_stages(env)
