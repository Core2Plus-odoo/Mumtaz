"""
Data Normalizer
===============
Cleans and validates raw extracted lead data.
"""

import re

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
URL_RE = re.compile(r"^https?://[^\s]{4,}$")

_JUNK_EMAILS = {"example.com", "domain.com", "test.com", "youremail.com", "email.com"}


class Normalizer:
    """Cleans and validates a ParsedLead dict."""

    def normalize(self, parsed_lead):
        """
        Normalize a ParsedLead instance.
        Returns a clean dict ready for lead.scraper.record creation,
        or None if the record has no usable data.
        """
        import json

        data = {
            "company_name": self._text(parsed_lead.company_name),
            "contact_name": self._text(parsed_lead.contact_name),
            "email": self._email(parsed_lead.email),
            "phone": self._phone(parsed_lead.phone),
            "website": self._url(parsed_lead.website),
            "city": self._text(parsed_lead.city),
            "country_name": self._text(parsed_lead.country_name),
            "industry": self._text(parsed_lead.industry),
            "source_url": (parsed_lead.source_url or "")[:500],
            "description": self._text(parsed_lead.description, max_len=1000),
            "raw_payload": (
                json.dumps(parsed_lead.raw_payload)
                if isinstance(parsed_lead.raw_payload, dict)
                else str(parsed_lead.raw_payload or "")
            )[:2000],
        }

        if not any([data["email"], data["phone"], data["company_name"]]):
            return None

        return data

    # ── Field cleaners ────────────────────────────────────────────────────

    def _text(self, value, max_len=200):
        if not value:
            return ""
        cleaned = re.sub(r"\s+", " ", str(value)).strip()
        cleaned = re.sub(r"[^\w\s\-\.,&@()'\"\/\+]+", "", cleaned)
        return cleaned[:max_len]

    def _email(self, value):
        if not value:
            return ""
        value = str(value).strip().lower()
        domain = value.split("@")[-1] if "@" in value else ""
        if domain in _JUNK_EMAILS:
            return ""
        if any(junk in value for junk in ["example", "noreply", "no-reply", "donotreply"]):
            return ""
        return value if EMAIL_RE.match(value) else ""

    def _phone(self, value):
        if not value:
            return ""
        cleaned = re.sub(r"[^\d\+\-\s\(\)\.x]", "", str(value)).strip()
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) < 6 or len(digits) > 15:
            return ""
        return cleaned[:30]

    def _url(self, value):
        if not value:
            return ""
        value = str(value).strip()
        if not value.startswith(("http://", "https://")):
            value = "https://" + value
        return value[:500] if URL_RE.match(value) else ""
