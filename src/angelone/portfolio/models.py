from dataclasses import dataclass


@dataclass
class Holding:
    scheme_code: str
    isin: str
    scheme_name: str
    category: str
    current_value: float
    invested_value: float
    returns_value: float
    returns_percentage: float
    xirr_percentage: float
    units: float
    average_nav: float
    current_nav: float