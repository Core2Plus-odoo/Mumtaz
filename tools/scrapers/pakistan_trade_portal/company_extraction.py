import re
from collections import defaultdict
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from normalize import clean_text, extract_city, normalize_price, normalize_moq
from selectors import SECTOR_KEYWORDS


def infer_sector_from_text(text: str) -> str:
    lower = text.lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lower:
                return sector
    return ''


def find_company_candidates(soup: BeautifulSoup):
    candidates = []
    for a in soup.find_all('a', href=True):
        text = clean_text(a.get_text(' ', strip=True))
        href = a.get('href', '').strip()
        if not text or len(text) < 3:
            continue
        if any(k in href.lower() for k in ['company', 'supplier', 'seller', 'store']):
            candidates.append((text, href))
    return candidates


def extract_company_profile(url: str, soup: BeautifulSoup) -> dict:
    text = clean_text(soup.get_text(' ', strip=True))
    lines = [clean_text(x) for x in soup.get_text('\n').split('\n') if clean_text(x)]

    company_name = ''
    for line in lines[:30]:
        if 3 < len(line) < 120 and not any(x in line.lower() for x in ['login', 'register', 'home', 'search']):
            company_name = line
            break

    city = extract_city(text)
    sector = infer_sector_from_text(text)

    prices = []
    moqs = []
    products = []

    for line in lines:
        low = line.lower()
        if 'ask for price' in low or 'price' in low or 'usd' in low or 'pkr' in low:
            prices.append(normalize_price(line))
        if 'min' in low and ('qty' in low or 'quantity' in low):
            moqs.append(normalize_moq(line))
        if 8 < len(line) < 150 and not any(x in low for x in ['copyright', 'privacy', 'terms', 'login', 'register']):
            products.append(line)

    unique_products = []
    seen = set()
    for product in products:
        key = product.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_products.append(product)
        if len(unique_products) >= 10:
            break

    return {
        'company_name': company_name,
        'city': city,
        'sector': sector,
        'company_url': url,
        'sample_products': unique_products,
        'product_count_hint': len(unique_products),
        'pricing_visibility': 'visible' if prices else 'hidden',
        'price_examples': prices[:5],
        'moq_examples': moqs[:5],
        'source_text_preview': text[:500],
    }


def consolidate_company_records(product_records: list) -> list:
    grouped = defaultdict(list)
    for record in product_records:
        key = (record.get('company_name') or '', record.get('company_url') or '')
        grouped[key].append(record)

    companies = []
    for (company_name, company_url), rows in grouped.items():
        first = rows[0]
        products = []
        for row in rows:
            name = row.get('product_name')
            if name and name not in products:
                products.append(name)
        companies.append({
            'company_name': company_name,
            'company_url': company_url,
            'city': first.get('city', ''),
            'sector': first.get('sector', ''),
            'pricing_visibility': first.get('pricing_visibility', 'unknown'),
            'product_count_hint': len(products),
            'sample_products': products[:10],
            'qualification': first.get('qualification', 'C'),
            'score': first.get('total_score', 0),
            'likely_need': first.get('likely_need', ''),
            'target_offer': first.get('target_offer', ''),
        })

    return companies
