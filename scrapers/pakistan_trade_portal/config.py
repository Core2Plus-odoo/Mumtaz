import os

BASE_URL = "https://www.pakistantradeportal.gov.pk/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
}
DELAY_SECONDS = 1
MAX_PAGES = 5
TIMEOUT_SECONDS = 30
MAX_RETRIES = 2
BACKOFF_FACTOR = 0.5

# Optional XML-RPC Odoo target for CRM lead creation.
ODOO_URL = os.getenv("ODOO_URL", "")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")
