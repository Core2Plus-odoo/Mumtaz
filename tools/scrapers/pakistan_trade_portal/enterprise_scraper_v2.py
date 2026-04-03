import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import BASE_URL, HEADERS, DELAY_SECONDS
from models import RawTradeRecord, ScoredTradeLead
from scoring import score_lead
from selectors import SECTOR_KEYWORDS
from normalize import clean_text, extract_city


class EnterpriseScraperV2:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.visited = set()

    def get_soup(self, url):
        res = self.session.get(url, timeout=30)
        res.raise_for_status()
        return BeautifulSoup(res.text, 'lxml')

    def infer_sector(self, text):
        for sector, keys in SECTOR_KEYWORDS.items():
            for k in keys:
                if k in text.lower():
                    return sector
        return ''

    def extract_from_page(self, url):
        soup = self.get_soup(url)
        text = clean_text(soup.get_text())

        record = RawTradeRecord(
            company_name='',
            city=extract_city(text),
            sector=self.infer_sector(text),
            product_name=text[:150],
            source_url=url
        )

        scored = ScoredTradeLead(**record.to_dict())
        return score_lead(scored)

    def crawl(self):
        soup = self.get_soup(BASE_URL)
        links = [urljoin(BASE_URL, a['href']) for a in soup.find_all('a', href=True)]

        results = []

        for link in links[:200]:
            if link in self.visited:
                continue

            try:
                rec = self.extract_from_page(link)
                results.append(rec.__dict__)
                self.visited.add(link)
                time.sleep(DELAY_SECONDS)
            except Exception:
                continue

        return results


if __name__ == '__main__':
    s = EnterpriseScraperV2()
    data = s.crawl()
    print(len(data))
