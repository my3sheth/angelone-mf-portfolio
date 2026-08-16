from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from .client import AngelOneAPIClient


class HoldingsAPI:

    def __init__(self, client=None):
        self.client = client or AngelOneAPIClient()

    def get_holdings(self):
        """
        Fetch all mutual fund holdings using pagination.

        The authenticated URL captured by Playwright contains:
            offset=0
            limit=5

        We use the same authenticated endpoint and continue
        requesting pages until all holdings are retrieved.
        """

        captured_url = self.client.get_holdings_url()

        parsed = urlparse(captured_url)

        query = parse_qs(
            parsed.query,
            keep_blank_values=True,
        )

        limit = 5

        if "limit" in query:
            try:
                limit = int(query["limit"][0])
            except (ValueError, TypeError):
                limit = 5

        offset = 0

        all_holdings = []

        while True:

            query["offset"] = [str(offset)]
            query["limit"] = [str(limit)]

            page_url = urlunparse(
                parsed._replace(
                    query=urlencode(
                        query,
                        doseq=True,
                    )
                )
            )

            print(
                f"Fetching holdings page: "
                f"offset={offset}, limit={limit}"
            )

            response = self.client.get(
                page_url
            )

            payload = response.json()

            page_holdings = (
                payload.get("data")
                or []
            )

            if not page_holdings:
                break

            all_holdings.extend(
                page_holdings
            )

            metadata = (
                payload.get("metaData")
                or {}
            )

            total_count = metadata.get(
                "holdingCount"
            )

            # We know the total number of holdings.
            if (
                total_count is not None
                and len(all_holdings) >= total_count
            ):
                break

            # If fewer records than the page size
            # were returned, this is the final page.
            if len(page_holdings) < limit:
                break

            offset += limit

        # Remove accidental duplicate schemes.
        unique_holdings = {}

        for holding in all_holdings:

            key = (
                holding.get("isin"),
                holding.get("schemeCode"),
            )

            if key not in unique_holdings:
                unique_holdings[key] = holding

        result = list(
            unique_holdings.values()
        )

        print(
            f"Total unique mutual fund holdings: "
            f"{len(result)}"
        )

        return result

    def get_holding_detail(
        self,
        isin,
        scheme_code,
    ):

        url = (
            "https://nbu-mf-portfolio.angelone.in"
            f"/v2/portfolios/holdings/"
            f"{isin}/{scheme_code}"
        )

        params = {
            "holdingType": "INTERNAL",
        }

        response = self.client.get(
            url,
            params=params,
        )

        return response.json()