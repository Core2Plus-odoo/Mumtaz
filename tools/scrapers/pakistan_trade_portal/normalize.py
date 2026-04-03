import re


def clean_text(value: str) -> str:
    if not value:
        return ''
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def extract_city(text: str):
    cities = ['karachi','lahore','sialkot','faisalabad','gujranwala','islamabad']
    for c in cities:
        if c in text.lower():
            return c.title()
    return ''


def normalize_price(price: str):
    if not price:
        return ''
    return price.replace('\n', '').strip()


def normalize_moq(text: str):
    if not text:
        return ''
    if 'min' in text.lower() or 'qty' in text.lower():
        return text
    return ''
