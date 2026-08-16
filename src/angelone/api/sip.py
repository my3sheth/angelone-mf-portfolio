import os

from .client import AngelOneAPIClient


class SIPAPI:

    def __init__(self, client=None):
        self.client = client or AngelOneAPIClient()

    def get_sip(
        self,
        isin,
        scheme_code,
    ):

        url = "https://nbu-mf-core.angelone.in/v2/sips"

        params = {
            "isin": isin,
            "schemeCode": scheme_code,
            "InvestmentType": "SIP",
            "offset": 0,
            "limit": 35,
            "sortOrder": "default",
        }

        response = self.client.get(
            url,
            params=params,
        )

        # Some schemes may not have SIP information
        # or the endpoint may return an empty/non-JSON
        # response. Do not fail the entire portfolio.
        try:
            return response.json()

        except ValueError:

            print(
                f"  SIP data unavailable for "
                f"{scheme_code} ({isin})"
            )

            return {
                "status": "success",
                "data": {
                    "bookOverView": {},
                    "sips": [],
                    "summary": {},
                },
            }