from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class RawTradeRecord:
    company_name: str = ""
    city: str = ""
    sector: str = ""
    subcategory: str = ""
    product_name: str = ""
    price: str = ""
    min_qty: str = ""
    source_url: str = ""
    company_url: str = ""
    source_portal: str = "Pakistan Trade Portal"

    def to_dict(self):
        return asdict(self)


@dataclass
class ScoredTradeLead(RawTradeRecord):
    product_count_hint: int = 0
    pricing_visibility: str = "unknown"
    complexity_score: int = 0
    erp_fit_score: int = 0
    exporter_signal_score: int = 0
    total_score: int = 0
    likely_need: str = ""
    target_offer: str = ""
    qualification: str = "C"
    notes: Optional[str] = ""
