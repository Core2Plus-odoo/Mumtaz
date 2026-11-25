"""Keep credentials out of the database.

Two separate things live here and they are not equally strong.

``check_vault_ref`` is a format rule: a vault reference is a locator of the form
``vault://<collection>/<item>``, and anything else is refused. That is exact.

``refuse_secret`` is a heuristic: it catches the common ways a password ends up
in a text field (``password: x``, ``token=x``, a URL with ``user:pass@``, a PEM
key). It cannot recognise a bare password typed with no label, and it does not
claim to. The real control is that this module has no field whose purpose is to
hold a secret; the heuristic only catches the obvious slip.
"""
import re

from odoo import _
from odoo.exceptions import ValidationError

VAULT_REF_RE = re.compile(
    r"^vault://[A-Za-z0-9][A-Za-z0-9._-]{0,62}"
    r"(/[A-Za-z0-9][A-Za-z0-9._-]{0,62}){1,6}$")

SECRET_RE = re.compile(
    r"(pass(word|wd|phrase)?|pwd|secret|token|api[ _-]?key|private[ _-]?key)"
    r"\s*[:=]"
    r"|BEGIN [A-Z ]*PRIVATE KEY"
    r"|://[^/\s:@]+:[^/\s@]+@",
    re.IGNORECASE)


def check_vault_ref(value):
    if value and not VAULT_REF_RE.match(value):
        raise ValidationError(_(
            "A vault reference says where the credential is kept, in the form "
            "vault://collection/item. It is never the credential itself."))


def refuse_secret(label, value):
    if value and SECRET_RE.search(value):
        raise ValidationError(_(
            "%(label)s looks like it contains a password, key or token. "
            "Credentials are kept in the vault; record only the vault "
            "reference here.", label=label))
