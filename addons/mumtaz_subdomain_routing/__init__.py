from . import models
from . import controllers


def post_load():
    """Install the (gated) host→database db_filter override at server start."""
    from . import patch
    patch.apply()
