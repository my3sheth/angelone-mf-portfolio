from dataclasses import dataclass

from .models import Holding


@dataclass
class PortfolioSummary:
    total_invested: float
    total_current: float
    total_returns: float
    absolute_return_percentage: float


def calculate_summary(holdings: list[Holding]) -> PortfolioSummary:
    total_invested = sum(h.invested_value for h in holdings)
    total_current = sum(h.current_value for h in holdings)
    total_returns = total_current - total_invested

    absolute_return_percentage = (
        (total_returns / total_invested) * 100
        if total_invested
        else 0.0
    )

    return PortfolioSummary(
        total_invested=total_invested,
        total_current=total_current,
        total_returns=total_returns,
        absolute_return_percentage=absolute_return_percentage,
    )