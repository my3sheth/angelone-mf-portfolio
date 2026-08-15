import json
import os

import requests
from dotenv import load_dotenv


load_dotenv()


class AngelOneAPIClient:
    def __init__(self):
        self.session = requests.Session()

        raw_headers = os.getenv("ANGELONE_MF_HEADERS")
        raw_cookies = os.getenv("ANGELONE_MF_COOKIES")

        if not raw_headers or not raw_cookies:
            raise RuntimeError(
                "Angel One authentication data is missing. "
                "Run scripts/login.py first."
            )

        headers = json.loads(raw_headers)
        cookies = json.loads(raw_cookies)

        # Browser-only headers should not be replayed.
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

    def get(self, url, params=None):
        response = self.session.get(
            url,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response