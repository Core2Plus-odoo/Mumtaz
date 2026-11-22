"""The model provider: the Claude Messages API over plain HTTP.

Plain `requests` rather than the SDK because the Odoo container is the
stock `odoo:19` image and installing packages into it is a production
change that needs its own approval. The key comes from the environment
only (`JAWHAR_ANTHROPIC_API_KEY`); it is never stored in the database and
never echoed. With no key the provider is simply "not configured" and
every agent capability takes its local path.
"""
import logging
import os
import time

import requests

_logger = logging.getLogger(__name__)

URL = 'https://api.anthropic.com/v1/messages'
API_VERSION = '2023-06-01'
# Refusal fallbacks route a declined request to a fallback model inside the
# same call, so a safety decline on routine retail copy does not become an
# outage.
BETAS = 'server-side-fallback-2026-07-01'
DEFAULT_MODEL = 'claude-opus-5-5'
TIMEOUT_S = 45
MAX_TOKENS = 1024

KEY_VAR = 'JAWHAR_ANTHROPIC_API_KEY'
MODEL_VAR = 'JAWHAR_AI_MODEL'


class ProviderError(Exception):
    pass


def configured():
    return bool(os.environ.get(KEY_VAR))


def model_name():
    return os.environ.get(MODEL_VAR) or DEFAULT_MODEL


def complete(system, user_text, max_tokens=MAX_TOKENS):
    """One turn: a system prompt and one user message, prose back.

    Returns dict(text, model, input_tokens, output_tokens, refused) or
    raises ProviderError. A refusal is not an error: it comes back with
    `refused` set and empty text, and the caller takes the local path.
    """
    key = os.environ.get(KEY_VAR)
    if not key:
        raise ProviderError('not_configured')
    body = {
        'model': model_name(),
        'max_tokens': max_tokens,
        'system': system,
        'messages': [{'role': 'user', 'content': user_text}],
        'output_config': {'effort': 'low'},
        'fallbacks': 'default',
    }
    started = time.monotonic()
    try:
        resp = requests.post(
            URL, json=body, timeout=TIMEOUT_S,
            headers={'x-api-key': key, 'anthropic-version': API_VERSION,
                     'anthropic-beta': BETAS, 'content-type': 'application/json'})
    except requests.exceptions.RequestException as exc:
        raise ProviderError('network:%s' % exc.__class__.__name__)
    if resp.status_code != 200:
        # The body may carry our own prompt back; log the status only.
        _logger.warning('Jawhar AI: provider returned HTTP %s', resp.status_code)
        raise ProviderError('http_%s' % resp.status_code)
    data = resp.json()
    usage = data.get('usage') or {}
    out = {
        'text': ''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text').strip(),
        'model': data.get('model') or model_name(),
        'input_tokens': int(usage.get('input_tokens') or 0),
        'output_tokens': int(usage.get('output_tokens') or 0),
        'refused': data.get('stop_reason') == 'refusal',
        'duration_ms': int((time.monotonic() - started) * 1000),
    }
    if out['refused']:
        out['text'] = ''
    return out
