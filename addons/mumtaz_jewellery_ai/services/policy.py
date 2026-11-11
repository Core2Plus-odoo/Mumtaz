"""The agent policy, pure Python: what the agents are, what each tool may
do, what may enter a model request, and the check that a model sentence
carries no number the tools did not supply. No Odoo imports, so the
engine tests run it without a database.

Autonomy levels (plan v3 section 13): A read, B recommend, C draft,
D execute with named approval, E prohibited.
"""
import re

POLICY_VERSION = 'agents-1'

RESTRICTED = ('private', 'royal')

AGENTS = {
    'zayan': {
        'name': 'Zayan', 'role': 'coordinator', 'ceiling': 'B',
        'purpose': 'The morning brief, the decision queue and the command bar: '
                   'reads the engine, explains, routes. Never approves, never prices.',
    },
    'layla': {
        'name': 'Layla', 'role': 'client & retail', 'ceiling': 'C',
        'purpose': 'Prepares a Private Tray through the same ranking staff use and '
                   'drafts the follow-up a person reviews and sends. Never sends.',
    },
}

# The tool registry. Every agent action goes through one of these; the
# level is the ceiling of the action, not of the agent, and a tool is only
# ever run as the signed-in user, so row and field access apply as they do
# on every screen.
TOOLS = {
    'rate.current': dict(agent='zayan', level='A', purpose='The approved gold rate, with who approved it and when.'),
    'today.figures': dict(agent='zayan', level='A', purpose='The figures on Today, each with its source.'),
    'decisions.queue': dict(agent='zayan', level='A', purpose='What waits for a person: owner cards and drafts.'),
    'brief.prepare': dict(agent='zayan', level='B', purpose='The morning brief: figures, the queue, what to do first.'),
    'intent.route': dict(agent='zayan', level='A', purpose='Classify a request and route it to a tool.'),
    'tray.prepare': dict(agent='layla', level='C', purpose='Build a Private Tray from eligible stock, reasons attached.'),
    'followup.draft': dict(agent='layla', level='C', purpose='Draft a follow-up for a person to review and send.'),
}

# What a request is about, decided locally first. Each intent lists the
# words (English and Arabic) that name it; the model is asked only when none
# of these match, and only to classify, never to act.
INTENTS = {
    'brief': ('brief', 'my day', 'prepare my day', 'morning', 'today', 'يوم', 'ملخص', 'صباح', 'إيجاز'),
    'tray': ('tray', 'selection', 'pieces for', 'prepare for', 'صينية', 'تشكيلة', 'قطع'),
    'followup': ('follow', 'message', 'note to', 'draft', 'write to', 'رسالة', 'متابعة'),
    'rate': ('rate', 'gold price', 'سعر', 'الذهب'),
    'queue': ('decision', 'waiting', 'approve', 'queue', 'pending', 'قرار', 'موافقة', 'انتظار'),
}

_NUMBER = re.compile(r'\d[\d,.٫٬٠-٩]*')


def classify(text):
    """Local intent: the first intent whose words appear, 'unknown' otherwise."""
    t = (text or '').strip().lower()
    if not t:
        return 'unknown'
    for intent, words in INTENTS.items():
        if any(w in t for w in words):
            return intent
    return 'unknown'


def client_hint(text):
    """The part of a request that names the client: what follows 'for' or
    'to' (or the Arabic 'لـ'), stripped of filler. None when there is none."""
    t = (text or '').strip()
    for sep in (' for ', ' to ', ' لـ', ' ل '):
        if sep in t:
            hint = t.split(sep, 1)[1]
            hint = re.split(r'[,.?!]|\b(?:about|with|on|regarding)\b', hint, 1)[0]
            return hint.strip(' "\'') or None
    return None


def may_enter_model(partner_facts):
    """A Private or Royal client never enters a model request. The caller
    passes the facts it means to send; the answer is a reason or None."""
    tier = (partner_facts or {}).get('tier')
    if tier in RESTRICTED:
        return 'restricted_client'
    return None


def numbers_in(text):
    """The digit groups in a text, normalised (Arabic-Indic digits and
    separators folded) so '6,491.84' and '6491.84' compare equal."""
    out = set()
    for m in _NUMBER.findall(text or ''):
        s = m.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩٫٬', '0123456789.,')).replace(',', '').strip('.')
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        if s and any(ch.isdigit() for ch in s):
            out.add(s)
    return out


def numbers_are_sourced(text, facts_text):
    """True when every number in the model's text appears in the facts the
    tools supplied. A number the tools did not supply is a number the model
    produced, and that is the one thing it may not do."""
    allowed = numbers_in(facts_text)
    return all(any(n == a or (len(n) >= 2 and n in a) for a in allowed) for n in numbers_in(text))
