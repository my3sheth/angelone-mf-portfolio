from dataclasses import dataclass


@dataclass
class PortfolioHolding:
    scheme_code: str
    isin: str
    scheme_name: str

    current_value: float
    invested_value: float
    returns_value: float
    returns_absolute_percent: float
    xirr_percent: float

    total_units: float
    average_nav: float
    current_nav: float

    category: str
    subcategory: str

    benchmark_name: str
    benchmark_return_percent: float

    sip_enabled: bool
    next_sip_date: int | None

    last_updated_date: str