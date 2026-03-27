import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

from config import BASE_URL, HEADERS, DELAY_SECONDS
from models import RawTradeRecord, ScoredTradeLead
from scoring import score_lead


def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def scrape_homepage():
    soup = get_soup(BASE_URL)
    records = []

    cards = soup.find_all("a", href=True)

    for a in cards:
        text = a.get_text(strip=True)
        href = a["href"]

        if not text or len(text) < 5:
            continue

        record = RawTradeRecord(
            product_name=text,
            source_url=href
        )

        scored = ScoredTradeLead(**record.to_dict())
        scored = score_lead(scored)

        records.append(scored.__dict__)

    return records


def main():
    data = scrape_homepage()

    df = pd.DataFrame(data)
    df.to_csv("output_leads.csv", index=False)

    print(f"Saved {len(df)} leads")


if __name__ == "__main__":
    main()
