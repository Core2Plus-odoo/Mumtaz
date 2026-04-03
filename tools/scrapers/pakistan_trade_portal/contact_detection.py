import re
from normalize import clean_text


EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PHONE_RE = re.compile(r'(\+92[\-\s]?[0-9\-\s]{7,15}|0[0-9\-\s]{9,15})')

EXPORTER_KEYWORDS = [
    'export', 'exporter', 'exports', 'international market', 'overseas',
    'global market', 'shipment', 'shipments', 'buyer', 'buyers', 'import export'
]

CERTIFICATION_KEYWORDS = [
    'iso', 'ce', 'fda', 'gmp', 'halal', 'organic', 'registered', 'certified'
]


def extract_contacts(text: str) -> dict:
    cleaned = clean_text(text)
    emails = sorted(set(EMAIL_RE.findall(cleaned)))
    phones = []
    for match in PHONE_RE.findall(cleaned):
        normalized = clean_text(match)
        if normalized not in phones:
            phones.append(normalized)
    return {
        'emails': emails[:5],
        'phones': phones[:5],
        'has_contact': bool(emails or phones),
    }


def detect_exporter_signals(text: str) -> dict:
    lower = text.lower()
    matches = [k for k in EXPORTER_KEYWORDS if k in lower]
    certs = [k for k in CERTIFICATION_KEYWORDS if k in lower]

    exporter_score = 0
    exporter_score += min(len(matches) * 15, 45)
    exporter_score += min(len(certs) * 10, 30)

    export_status = 'unknown'
    if exporter_score >= 40:
        export_status = 'strong'
    elif exporter_score >= 15:
        export_status = 'possible'

    return {
        'exporter_signal_score': exporter_score,
        'exporter_keywords_found': matches[:10],
        'certifications_found': certs[:10],
        'export_status': export_status,
    }
