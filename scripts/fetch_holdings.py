import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from angelone.api.holdings import HoldingsAPI
from angelone.portfolio.mapper import map_holdings
from angelone.portfolio.summary import calculate_summary


def main():
    print("Fetching mutual fund holdings...")

    response = HoldingsAPI().get_holdings()

    # Angel One response structure
    raw_holdings = response.get("data", response)

    holdings = map_holdings(raw_holdings)

    summary = calculate_summary(holdings)

    print("\nPortfolio Summary")
    print("-----------------")
    print(f"Invested : ₹{summary.total_invested:,.2f}")
    print(f"Current  : ₹{summary.total_current:,.2f}")
    print(f"Returns  : ₹{summary.total_returns:,.2f}")
    print(f"Return % : {summary.absolute_return_percentage:.2f}%")

    print(f"\nNumber of holdings: {len(holdings)}\n")

    for holding in holdings:
        print(json.dumps(holding.__dict__, indent=2))


if __name__ == "__main__":
    main()