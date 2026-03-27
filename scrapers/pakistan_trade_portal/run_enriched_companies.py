import pandas as pd
from enterprise_scraper_v2 import EnterpriseScraperV2
from company_extraction import consolidate_company_records
from company_enrichment import enrich_company


def main():
    scraper = EnterpriseScraperV2()
    product_records = scraper.crawl()

    companies = consolidate_company_records(product_records)

    enriched = [enrich_company(c) for c in companies]

    df = pd.DataFrame(enriched)
    df.to_csv('enriched_company_leads.csv', index=False)

    print(f"Enriched companies: {len(df)}")


if __name__ == '__main__':
    main()
