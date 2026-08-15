from typing import Any

import requests


class AngelOneAPIClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response