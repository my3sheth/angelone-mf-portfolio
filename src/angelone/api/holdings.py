from typing import Any

from angelone.api.client import AngelOneAPIClient


class HoldingsAPI:
    BASE_URL = "https://nbu-mf-portfolio.angelone.in"

    def __init__(self, client: AngelOneAPIClient) -> None:
        self.client = client

    def get_holdings(
        self,
        offset: int = 0,
        limit: int = 100,
        holding_type: str = "ALL",
        order_by: str = "current_value",
    ) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.BASE_URL}/v2/portfolios/holdings",
            params={
                "offset": offset,
                "limit": limit,
                "holdingType": holding_type,
                "orderBy": order_by,
            },
        )

        payload = response.json()

        if payload.get("status") != "success":
            raise RuntimeError(
                "Angel One holdings API returned an unsuccessful response"
            )

        data = payload.get("data", {})

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return data.get("holdings", [])

        return []