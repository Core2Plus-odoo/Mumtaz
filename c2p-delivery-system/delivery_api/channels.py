"""Channel adapters — email / WhatsApp / LinkedIn behind one clean interface.

Sending is **dry-run by default**: with no provider credentials configured it
records the message and returns mode='dry-run' (nothing leaves the building).
Configure provider creds in the environment to go live — the call sites do not
change. This keeps the approval layer honest: an approved send always runs the
same `send()`, whether dry-run or live.

Live config (optional):
  Email (SMTP):  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
  WhatsApp:      WHATSAPP_TOKEN, WHATSAPP_PHONE_ID   (Meta Cloud API)
"""
from __future__ import annotations

import logging
import os

_log = logging.getLogger("c2p.channels")


def _email_live() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def _whatsapp_live() -> bool:
    return bool(os.getenv("WHATSAPP_TOKEN") and os.getenv("WHATSAPP_PHONE_ID"))


def _send_email(to: str, subject: str, body: str) -> dict:
    if not _email_live():
        _log.info("[dry-run email] to=%s subject=%s", to, subject)
        return {"sent": False, "channel": "email", "to": to, "mode": "dry-run"}
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = to
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.starttls()
        if os.getenv("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        s.send_message(msg)
    return {"sent": True, "channel": "email", "to": to, "mode": "live"}


def _send_whatsapp(to: str, body: str) -> dict:
    if not _whatsapp_live():
        _log.info("[dry-run whatsapp] to=%s", to)
        return {"sent": False, "channel": "whatsapp", "to": to, "mode": "dry-run"}
    import json
    import urllib.request
    url = f"https://graph.facebook.com/v20.0/{os.environ['WHATSAPP_PHONE_ID']}/messages"
    data = json.dumps({
        "messaging_product": "whatsapp", "to": to,
        "type": "text", "text": {"body": body},
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        ok = resp.status in (200, 201)
    return {"sent": ok, "channel": "whatsapp", "to": to, "mode": "live"}


def send(channel: str, to: str, subject: str, body: str) -> dict:
    """One entry point for every gated send. Returns a result dict (never raises
    on dry-run; logs and returns on live failure)."""
    channel = (channel or "email").lower()
    try:
        if channel == "whatsapp":
            return _send_whatsapp(to, body)
        if channel == "linkedin":
            # No public send API — always queued as a manual/dry-run task.
            _log.info("[dry-run linkedin] to=%s", to)
            return {"sent": False, "channel": "linkedin", "to": to, "mode": "dry-run",
                    "note": "LinkedIn has no send API; deliver manually."}
        return _send_email(to, subject, body)
    except Exception as exc:  # noqa: BLE001 - surface as a result, not a crash
        _log.exception("send failed channel=%s to=%s", channel, to)
        return {"sent": False, "channel": channel, "to": to, "mode": "error",
                "error": str(exc)}
