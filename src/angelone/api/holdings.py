import os

from .client import AngelOneAPIClient


class HoldingsAPI:
    def __init__(self, client=None):
        self.client = client or AngelOneAPIClient()

    def get_holdings(self):
        url = os.environ["ANGELONE_MF_URL"]

        return self.client.get(url).json()