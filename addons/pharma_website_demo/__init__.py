from . import models


def post_init_hook(env):
    env["pharma.website.demo.seed"].seed()
