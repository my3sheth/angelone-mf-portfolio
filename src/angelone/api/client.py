import json
import os

import requests
from dotenv import load_dotenv


class AngelOneAPIClient:

    def __init__(self):
        # Always reload the latest values written to .env
        load_dotenv(override=True)

        self.session = requests.Session()

        raw_headers = os.getenv("ANGELONE_MF_HEADERS")
        raw_cookies = os.getenv("ANGELONE_MF_COOKIES")

        if not raw_headers or not raw_cookies:
            raise RuntimeError(
                "Angel One authentication data is missing. "
                "Run authentication first."
            )

        try:
            headers = json.loads(raw_headers)
            cookies = json.loads(raw_cookies)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Stored Angel One authentication data is invalid."
            ) from exc

        # Headers that must NOT be replayed manually.
        excluded_headers = {
            "host",
            "content-length",
            "connection",
            "cookie",
        }

        for key, value in headers.items():
            if key.lower() not in excluded_headers:
                self.session.headers[key] = value

        for cookie in cookies:
            self.session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

    def get_holdings_url(self):
        """
        Return the authenticated MF holdings endpoint
        captured during browser login.
        """

        load_dotenv(override=True)

        url = os.getenv("ANGELONE_MF_URL")

        if not url:
            raise RuntimeError(
                "ANGELONE_MF_URL is missing from .env. "
                "Run authentication first."
            )

        return url

    def get(self, url, params=None):

        response = self.session.get(
            url,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response