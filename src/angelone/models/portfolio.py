from typing import Optional

from pydantic import BaseModel


class MutualFundHolding(BaseModel):

    scheme_name: str

    folio_no: list[str]

    sip_date: Optional[int] = None

    start_date: Optional[str] = None

    monthly_sip: Optional[float] = None

    total_invested: Optional[float] = None

    current_units: Optional[float] = None

    current_nav: Optional[float] = None

    ter: Optional[float] = None


class PortfolioResponse(BaseModel):

    holdings_count: int

    holdings: list[MutualFundHolding]