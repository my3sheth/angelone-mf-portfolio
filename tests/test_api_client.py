from unittest.mock import Mock

import pytest
import requests

from angelone.api.client import AngelOneAPIClient
from angelone.auth.session import AuthenticatedSession


def test_get_returns_successful_response():
    session = Mock(spec=requests.Session)

    response = Mock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    session.get.return_value = response

    client = AngelOneAPIClient(session=session)

    result = client.get("https://example.com/test")

    session.get.assert_called_once_with("https://example.com/test")
    response.raise_for_status.assert_called_once()
    assert result is response


def test_get_raises_for_http_error():
    session = Mock(spec=requests.Session)

    response = Mock()
    response.status_code = 401
    response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")

    session.get.return_value = response

    client = AngelOneAPIClient(session=session)

    with pytest.raises(requests.HTTPError):
        client.get("https://example.com/test")
