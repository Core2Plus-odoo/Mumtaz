from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

_FIELDS = {"proof": "proof_image", "receipt": "receipt_image"}


class FaizyEvidence(http.Controller):
    """The one reviewed place where a customer can see an evidence image.

    The image fields are staff-only. This route first runs the order's own
    record rule as the logged-in user (a foreign order id is a 404, never a
    leak), then serves the image only when the reviewer has approved it. The
    sudo() below is the only one in this addon and is limited to reading that
    single binary field for an order the user was already allowed to read.
    """

    @http.route("/faizy/evidence/<int:order_id>/<string:kind>", type="http", auth="user")
    def evidence_image(self, order_id, kind, **kw):
        field = _FIELDS.get(kind)
        if not field:
            return request.not_found()
        order = request.env["faizy.order"].browse(order_id)
        try:
            order.check_access("read")
            order.read(["name"])  # forces the record rule to run
        except (AccessError, MissingError):
            return request.not_found()
        if order.evidence_state != "approved":
            return request.not_found()
        record = order.sudo()
        if not record[field]:
            return request.not_found()
        stream = request.env["ir.binary"].sudo()._get_image_stream_from(
            record, field_name=field, filename="%s-%s.png" % (order.name, kind)
        )
        return stream.get_response(as_attachment=False, max_age=0)
