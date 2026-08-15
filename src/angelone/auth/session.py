import os

import requests
from dotenv import load_dotenv


class AuthenticatedSession:
    def __init__(self) -> None:
        load_dotenv()

        non_trade = os.getenv("ANGELONE_NON_TRADE_ACCESS_TOKEN")
        trade = os.getenv("ANGELONE_TRADE_ACCESS_TOKEN")

        if not non_trade or not trade:
            raise RuntimeError(
                "Angel One authentication tokens are not configured."
            )

        self.session = requests.Session()

        self.session.cookies.set(
            "prod_non_trade_access_token",
            non_trade,
            domain=".angelone.in",
            path="/",
        )
        self.session.cookies.set(
            "prod_trade_access_token",
            trade,
            domain=".angelone.in",
            path="/",
        )

    def get_session(self) -> requests.Session:
        return self.session