import json

import requests

from angelone.auth_store import load_auth_details, mark_auth_expired
from angelone.session_store import get_active_account_name


class AngelOneAPIClient:

    def __init__(self, account_name=None):
        self.account_name = account_name or get_active_account_name()
        if not self.account_name:
            raise RuntimeError(
                "No active account selected. Please log in or pick an account first."
            )

        auth_details = load_auth_details(self.account_name)
        if not auth_details:
            raise RuntimeError(
                f"Angel One authentication data is missing for account '{self.account_name}'. "
                "Run authentication first."
            )

        self.session = requests.Session()
        headers = auth_details.get("headers") or {}
        cookies = auth_details.get("cookies") or []

        if not isinstance(headers, dict) or not isinstance(cookies, list):
            raise RuntimeError(
                f"Stored Angel One authentication data for '{self.account_name}' is invalid."
            )

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
                cookie.get("name"),
                cookie.get("value"),
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

    def get_holdings_url(self):
        """
        Return the authenticated MF holdings endpoint
        captured during browser login.
        """
        auth_details = load_auth_details(self.account_name or get_active_account_name())
        url = (auth_details or {}).get("url")

        if not url:
            raise RuntimeError(
                f"Authentication URL is missing for account '{self.account_name}'. "
                "Run authentication first."
            )

        return url

    def get(self, url, params=None):
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response
        except requests.HTTPError as err:
            if err.response is not None and err.response.status_code in (401, 403):
                try:
                    mark_auth_expired(self.account_name)
                except Exception:
                    pass
            raise