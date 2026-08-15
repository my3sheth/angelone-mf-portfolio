from angelone.api.client import AngelOneAPIClient
from angelone.api.holdings import HoldingsAPI
from angelone.auth.session import AuthenticatedSession
from angelone.models.holding_mapper import map_holding


def main() -> None:
    auth = AuthenticatedSession()
    client = AngelOneAPIClient(auth.get_session())
    holdings_api = HoldingsAPI(client)

    raw_holdings = holdings_api.get_holdings()
    holdings = [map_holding(item) for item in raw_holdings]

    print(f"Number of holdings: {len(holdings)}")

    for holding in holdings:
        print(
            holding.scheme_name,
            "| invested:", holding.invested_value,
            "| current:", holding.current_value,
            "| XIRR:", holding.xirr_percent,
        )


if __name__ == "__main__":
    main()