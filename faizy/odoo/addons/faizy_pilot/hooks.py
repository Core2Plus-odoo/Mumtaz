from .models.faizy_order import _TOKEN


def post_init_hook(env):
    """Give orders that already hold evidence a sensible starting state.

    Orders that existed before this addon have images but evidence_state 'none'.
    Without this, customers would lose sight of the proof and receipt on orders
    that were already completed (and already visible), and in-progress orders
    with a photo could neither be approved nor completed without re-uploading.

    - completed with an image  -> approved (they were already completed and
      already visible to the customer; marked in the chatter, no reviewer)
    - any other state with an image -> submitted (goes to a human review)
    Runs once, on first install only. Orders without images are untouched.
    """
    env.cr.execute(
        """
        SELECT DISTINCT res_id FROM ir_attachment
         WHERE res_model = 'faizy.order'
           AND res_field IN ('proof_image', 'receipt_image')
           AND res_id IS NOT NULL
        """
    )
    ids = [row[0] for row in env.cr.fetchall()]
    orders = env["faizy.order"].sudo().browse(ids).exists().with_context(
        tracking_disable=True, faizy_evidence_internal=_TOKEN
    )
    for order in orders.filtered(lambda o: o.evidence_state == "none"):
        if order.state == "completed":
            order.write({"evidence_state": "approved"})
            order.message_post(body=env._(
                "Evidence marked approved when the evidence gate was installed: "
                "this order was already completed before review existed."))
        else:
            order.write({"evidence_state": "submitted"})
