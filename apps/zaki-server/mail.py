"""
Lightweight SMTP email helper for Mumtaz.

Reads SMTP config from env. If SMTP_HOST is unset, falls back to
stdout logging — keeps signup working in dev without an SMTP server.

Env vars:
    SMTP_HOST     e.g. smtp.zoho.com
    SMTP_PORT     default 587
    SMTP_USER     login
    SMTP_PASS     password / app token
    SMTP_FROM     "Mumtaz <hello@mumtaz.digital>"
    SMTP_USE_TLS  "1" (default) or "0"
"""

import os, smtplib, ssl, traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _config():
    return {
        "host":    os.environ.get("SMTP_HOST", "").strip(),
        "port":    int(os.environ.get("SMTP_PORT", "587") or "587"),
        "user":    os.environ.get("SMTP_USER", "").strip(),
        "password":os.environ.get("SMTP_PASS", ""),
        "from":    os.environ.get("SMTP_FROM", "Mumtaz <hello@mumtaz.digital>").strip(),
        "use_tls": os.environ.get("SMTP_USE_TLS", "1") != "0",
    }


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Send a transactional email. Returns True on success, False otherwise.
    Never raises — failures are logged and ignored so they don't break signup."""
    cfg = _config()
    if not cfg["host"]:
        print(f"[mail] SMTP_HOST not configured — would send to {to}: {subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"]    = cfg["from"]
    msg["To"]      = to
    msg["Subject"] = subject
    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if cfg["use_tls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
                s.starttls(context=ssl.create_default_context())
                if cfg["user"]:
                    s.login(cfg["user"], cfg["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15,
                                  context=ssl.create_default_context()) as s:
                if cfg["user"]:
                    s.login(cfg["user"], cfg["password"])
                s.send_message(msg)
        print(f"[mail] sent → {to} · {subject}")
        return True
    except Exception as e:
        print(f"[mail] FAILED → {to} · {subject} · {e}")
        traceback.print_exc()
        return False


# ── Templates ────────────────────────────────────────────────────────

def welcome_email(name: str, email: str) -> tuple[str, str, str]:
    """Returns (subject, html, plain_text) for the new-account welcome."""
    first   = (name or email).split(" ")[0] or "there"
    subject = "Welcome to Mumtaz, " + first

    html = f"""<!DOCTYPE html>
<html><body style="margin:0;font-family:-apple-system,Segoe UI,sans-serif;background:#F5F3EF;color:#0C1118">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F3EF;padding:40px 20px">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;border:1px solid #E4E0D8">
      <tr><td style="padding:32px 40px 0">
        <div style="display:inline-block;width:40px;height:40px;background:linear-gradient(135deg,#B8862A,#D4A84C);border-radius:10px;text-align:center;line-height:40px;color:#fff;font-family:Georgia,serif;font-size:20px">م</div>
        <div style="display:inline-block;margin-left:10px;font-weight:600;font-size:18px;vertical-align:middle">Mumtaz</div>
      </td></tr>
      <tr><td style="padding:24px 40px 8px">
        <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-weight:400;font-size:28px;color:#0C1118">
          Welcome, {first}.
        </h1>
        <p style="margin:0 0 16px;color:#3D4A5C;font-size:15px;line-height:1.55">
          Thanks for signing up for Mumtaz — the GCC's all-in-one ERP, AI agent, and B2B marketplace.
        </p>
        <p style="margin:0 0 24px;color:#3D4A5C;font-size:15px;line-height:1.55">
          Take 90 seconds to tell us about your business and we'll auto-configure the right modules and AI agents for you.
        </p>
        <p style="margin:0 0 32px">
          <a href="https://app.mumtaz.digital/onboarding.html"
             style="display:inline-block;background:#B8862A;color:#fff;text-decoration:none;padding:12px 28px;border-radius:100px;font-weight:600;font-size:14px">
            Continue setup →
          </a>
        </p>
      </td></tr>
      <tr><td style="padding:0 40px 32px;border-top:1px solid #E4E0D8;padding-top:24px">
        <p style="margin:0 0 6px;font-family:'DM Mono',Menlo,monospace;font-size:11px;color:#7A8799;letter-spacing:.08em;text-transform:uppercase">
          What's included in your trial
        </p>
        <ul style="margin:0;padding-left:20px;color:#3D4A5C;font-size:14px;line-height:1.7">
          <li>All ERP modules — accounting, sales, inventory, HR, payroll</li>
          <li>1 ZAKI AI agent — your virtual CFO, marketing, ops or sales assistant</li>
          <li>Up to 3 users for 14 days, no credit card required</li>
        </ul>
      </td></tr>
      <tr><td style="padding:0 40px 32px">
        <p style="margin:0;color:#7A8799;font-size:13px;line-height:1.55">
          Questions? Reply to this email — we read every one.<br>
          — The Mumtaz team
        </p>
      </td></tr>
    </table>
    <p style="margin:16px 0 0;color:#7A8799;font-size:11px">
      You're receiving this because someone signed up at app.mumtaz.digital with {email}.
    </p>
  </td></tr>
</table>
</body></html>"""

    text = f"""Welcome to Mumtaz, {first}.

Thanks for signing up for Mumtaz — the GCC's all-in-one ERP, AI agent, and B2B marketplace.

Take 90 seconds to tell us about your business and we'll auto-configure the right modules and AI agents for you:

    https://app.mumtaz.digital/onboarding.html

What's included in your trial:
- All ERP modules — accounting, sales, inventory, HR, payroll
- 1 ZAKI AI agent
- Up to 3 users for 14 days, no credit card required

Questions? Reply to this email — we read every one.

— The Mumtaz team
"""
    return subject, html, text


def password_reset_email(name: str, reset_url: str) -> tuple[str, str, str]:
    first   = (name or "there").split(" ")[0]
    subject = "Reset your Mumtaz password"
    html = f"""<!DOCTYPE html>
<html><body style="margin:0;font-family:-apple-system,Segoe UI,sans-serif;background:#F5F3EF;color:#0C1118">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F3EF;padding:40px 20px">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;border:1px solid #E4E0D8">
      <tr><td style="padding:32px 40px">
        <div style="display:inline-block;width:40px;height:40px;background:linear-gradient(135deg,#B8862A,#D4A84C);border-radius:10px;text-align:center;line-height:40px;color:#fff;font-family:Georgia,serif;font-size:20px">م</div>
        <div style="display:inline-block;margin-left:10px;font-weight:600;font-size:18px;vertical-align:middle">Mumtaz</div>
      </td></tr>
      <tr><td style="padding:0 40px 24px">
        <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-weight:400;font-size:24px">
          Reset your password
        </h1>
        <p style="margin:0 0 20px;color:#3D4A5C;font-size:15px;line-height:1.55">
          Hi {first}, click the button below to set a new password. The link expires in 1 hour.
        </p>
        <p style="margin:0 0 24px">
          <a href="{reset_url}"
             style="display:inline-block;background:#B8862A;color:#fff;text-decoration:none;padding:12px 28px;border-radius:100px;font-weight:600;font-size:14px">
            Reset password →
          </a>
        </p>
        <p style="margin:0;color:#7A8799;font-size:13px;line-height:1.55">
          If you didn't request this, ignore this email — your password won't change.<br>
          Or copy and paste this URL: <span style="color:#3D4A5C">{reset_url}</span>
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""
    text = f"""Reset your Mumtaz password

Hi {first}, click the link below to set a new password. The link expires in 1 hour.

    {reset_url}

If you didn't request this, ignore this email — your password won't change.

— The Mumtaz team
"""
    return subject, html, text
