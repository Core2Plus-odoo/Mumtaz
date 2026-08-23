"""Address validation, cheapest check first.

Three layers, each only reached if the previous one passed:

1. **Syntax** — via Odoo's own ``email_normalize``. Free, instant, catches typos.
2. **Domain class** — free provider (valid, but a person not a business) or
   disposable (treated as invalid: nobody reads a 10-minute mailbox).
3. **Resolution** — does the domain actually accept mail. This is the layer that
   earns its keep: dead and misspelled domains are the main source of bounces,
   and bounces are what get a sending domain blocked.

A fourth layer — mailbox-level verification through a paid API — is where you go
when layers 1-3 pass but you still want to know the mailbox exists. It is not
implemented here; see ``verify_mailbox``.

Verdicts are deliberately three-valued. ``risky`` is not ``invalid``: a free
mailbox is perfectly deliverable, it just tells you something about the lead.
"""

import logging
import socket

from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

VALID = "valid"
RISKY = "risky"
INVALID = "invalid"

# Consumer mailboxes. Deliverable, so not invalid — but a business enquiry from
# one is worth knowing about, and the lead scorer reads the same list.
FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "hotmail.co.uk",
        "outlook.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "gmx.com",
        "yandex.com",
        "mail.ru",
        "rediffmail.com",
        "zoho.com",
    }
)

# Throwaway mailbox services. Mail sent here is never read, so it is all bounce
# risk and no upside.
DISPOSABLE_EMAIL_DOMAINS = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "10minutemail.com",
        "tempmail.com",
        "temp-mail.org",
        "throwawaymail.com",
        "yopmail.com",
        "trashmail.com",
        "getnada.com",
        "sharklasers.com",
        "dispostable.com",
        "maildrop.cc",
        "fakeinbox.com",
        "mailnesia.com",
        "spamgourmet.com",
        "mintemail.com",
        "tempr.email",
        "moakt.com",
    }
)


def address_domain(email):
    """The domain part of an address, tolerating "Name <a@b.com>"."""
    raw = (email or "").strip().lower()
    if "<" in raw and ">" in raw:
        raw = raw[raw.rfind("<") + 1 : raw.rfind(">")]
    return raw.rpartition("@")[2].strip()


def resolve_domain(domain, timeout=5.0):
    """Can this domain receive mail? Returns (ok, detail).

    Prefers a real MX lookup via dnspython. That is an optional dependency, so
    when it is absent this degrades to "does the domain resolve at all", which
    is weaker but still catches the dead and misspelled domains that cause most
    bounces. The detail string always records which of the two ran, so a result
    is never ambiguous about how much it proved.
    """
    try:
        import dns.resolver  # optional; see __manifest__ external_dependencies
    except ImportError:
        dns_resolver = None
    else:
        dns_resolver = dns.resolver

    if dns_resolver is not None:
        try:
            answers = dns_resolver.resolve(domain, "MX", lifetime=timeout)
            if len(answers):
                return True, "MX record found"
            return False, "domain has no MX record"
        except dns_resolver.NXDOMAIN:
            return False, "domain does not exist"
        except dns_resolver.NoAnswer:
            return False, "domain has no MX record"
        except Exception as exc:
            # A timeout or a broken resolver is not evidence the domain is bad.
            # Fall through to the weaker check rather than condemn the address.
            _logger.info("MX lookup for %s failed (%s), falling back", domain, exc)

    try:
        socket.getaddrinfo(domain, None)
        return True, "domain resolves (no MX check — dnspython not installed)"
    except socket.gaierror:
        return False, "domain does not resolve"
    except Exception as exc:
        _logger.info("Domain resolution for %s failed: %s", domain, exc)
        return True, "domain not checked (resolver unavailable)"


def validate_address(email, domain_cache=None, check_domain=True):
    """Run the layers in order. Returns ``(verdict, detail)``.

    ``domain_cache`` is an optional dict reused across a batch — a nightly run
    over 100 leads routinely sees the same domain many times, and this turns
    that into one lookup each.
    """
    if not (email or "").strip():
        return INVALID, "no address"

    normalized = email_normalize(email)
    if not normalized:
        return INVALID, "not a valid address"

    domain = address_domain(normalized)
    if not domain or "." not in domain:
        return INVALID, "no usable domain"

    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return INVALID, "disposable mailbox provider"

    if check_domain:
        if domain_cache is None:
            domain_cache = {}
        if domain not in domain_cache:
            domain_cache[domain] = resolve_domain(domain)
        ok, detail = domain_cache[domain]
        if not ok:
            return INVALID, detail
    else:
        detail = "syntax only (domain not checked)"

    if domain in FREE_EMAIL_DOMAINS:
        return RISKY, "free mailbox provider — %s" % detail

    return VALID, detail


def verify_mailbox(email):
    """Mailbox-level verification through a paid API. Not implemented.

    Layers 1-3 prove an address is well-formed and that its domain accepts mail.
    They cannot prove the mailbox itself exists — that needs a service such as
    ZeroBounce, NeverBounce or Hunter, which means an account, an API key and a
    per-check cost.

    Left unimplemented on purpose rather than guessed at: the request for it did
    not name a provider, and their APIs differ enough that a wrong choice is
    dead code with a credential handler attached. Wire it in here, have it
    return ``(verdict, detail)``, and call it from
    ``crm.lead._cron_validate_emails`` for addresses that already passed
    layers 1-3.
    """
    raise NotImplementedError(
        "No mailbox verification provider is configured. See the docstring."
    )
