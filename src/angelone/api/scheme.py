from .client import AngelOneAPIClient


BASE_URL = (
    "https://nbu-mf-instruments.angelone.in"
    "/v1/schemes"
)


class SchemeAPI:

    def __init__(self, client=None):
        self.client = client or AngelOneAPIClient()

    def get_scheme(self, isin, scheme_code):

        url = (
            f"{BASE_URL}/"
            f"{isin}/"
            f"{scheme_code}"
        )

        response = self.client.get(
            url,
            params={
                "isIncludeInactiveSchemes": "true",
            },
        )

        return response.json()