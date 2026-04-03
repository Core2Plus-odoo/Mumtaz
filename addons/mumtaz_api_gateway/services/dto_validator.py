from odoo.exceptions import ValidationError


def require_fields(payload, field_names):
    missing = [name for name in field_names if not payload.get(name)]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")
    return True
