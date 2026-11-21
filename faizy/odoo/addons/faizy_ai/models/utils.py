import re
from datetime import timezone
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.exceptions import AccessError

# Approved written format (Umer, 25 Oct 2026). Stale numbers must never reach a customer.
APPROVED_WHATSAPP = '+92 334 2726048'
FORBIDDEN_NUMBER_STRINGS = (
    '0334 272 6048', '0334 2726048', '03342726048', '0334-2726048',
    '03 343 043 970', '03343043970', '335 3043972', '3353043972',
)

G_AI = 'faizy_ai.group_ai_agent'
G_COMMS = 'faizy_ai.group_comms'
G_OPS = 'faizy_core.group_faizy_ops'
G_MANAGER = 'faizy_core.group_faizy_manager'


def get_param(env, key, default):
    return env['ir.config_parameter'].sudo().get_param(key, default)


def get_float(env, key, default):
    try:
        return float(get_param(env, key, default))
    except (TypeError, ValueError):
        return float(default)


def within_hours(env, dt=None):
    """True when dt (naive UTC, default now) falls inside Faizy working hours (Karachi)."""
    tz = ZoneInfo(get_param(env, 'faizy_ai.timezone', 'Asia/Karachi'))
    start = get_float(env, 'faizy_ai.hours_start', 10)
    end = get_float(env, 'faizy_ai.hours_end', 21)
    dt = dt or fields.Datetime.now()
    local = dt.replace(tzinfo=timezone.utc).astimezone(tz)
    return start <= local.hour + local.minute / 60.0 < end


def normalize_phone(raw):
    """Digits-only international form; Pakistani local 03xx... becomes 923xx..."""
    digits = re.sub(r'\D', '', raw or '')
    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = '92' + digits[1:]
    return digits


def has_stale_number(text):
    low = text or ''
    return [s for s in FORBIDDEN_NUMBER_STRINGS if s in low]


def is_approver(env):
    """Comms, operations, manager or system users, or a superuser context."""
    if env.su:
        return True
    user = env.user
    return any(user.has_group(g) for g in (G_COMMS, G_OPS, G_MANAGER, 'base.group_system'))


def can_approve(env, group_xmlid):
    if env.su:
        return True
    user = env.user
    return any(user.has_group(g) for g in (group_xmlid, G_MANAGER, 'base.group_system'))


def require_approver(env):
    if not is_approver(env):
        raise AccessError('AI agents can only draft. A person approves.')
