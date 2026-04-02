import pandas as pd
from enterprise_scraper_v2 import EnterpriseScraperV2
from company_extraction import consolidate_company_records


def main():
    scraper = EnterpriseScraperV2()
    product_records = scraper.crawl()

    companies = consolidate_company_records(product_records)

    df = pd.DataFrame(companies)
    df.to_csv('company_level_leads.csv', index=False)

    print(f"Companies extracted: {len(df)}")


if __name__ == '__main__':
    main()
