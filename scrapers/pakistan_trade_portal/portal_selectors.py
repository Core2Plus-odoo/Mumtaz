"""Selector constants for the Pakistan Trade Portal enrichment pipeline."""

# Broad selectors to stay resilient to small markup changes.
COMPANY_CARD_SELECTORS = [
    ".company-card",
    ".supplier-card",
    ".listing-item",
    "article",
    "li",
]

COMPANY_NAME_SELECTORS = [
    ".company-name",
    ".supplier-name",
    "h2",
    "h3",
    "a[title]",
    "a",
]

CITY_SELECTORS = [
    ".city",
    ".location",
    "[class*='city']",
    "[class*='location']",
]

SECTOR_SELECTORS = [
    ".sector",
    ".category",
    "[class*='sector']",
    "[class*='category']",
]
