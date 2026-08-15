import os

import requests
from dotenv import load_dotenv


load_dotenv()


class AuthenticatedSession:
    def __init__(self):
        non_trade_token = os.getenv("ANGELONE_NON_TRADE_ACCESS_TOKEN")
        trade_token = os.getenv("ANGELONE_TRADE_ACCESS_TOKEN")

        if not non_trade_token and not trade_token:
            raise RuntimeError(
                "authentication tokens are missing"
            )

        self.session = requests.Session()

        if non_trade_token:
            self.session.cookies.set(
                "prod_non_trade_access_token",
                non_trade_token,
                domain=".angelone.in",
            )

        if trade_token:
            self.session.cookies.set(
                "prod_trade_access_token",
                trade_token,
                domain=".angelone.in",
            )

    def get_session(self) -> requests.Session:
        return self.session