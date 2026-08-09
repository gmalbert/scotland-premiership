from unittest.mock import Mock, patch

import pytest
import requests

from scripts.fetch_odds import _get_json


def test_http_errors_do_not_include_api_key():
    response = Mock(ok=False, status_code=403, text='{"error":"forbidden"}')
    with patch("scripts.fetch_odds.requests.get", return_value=response):
        with pytest.raises(RuntimeError) as caught:
            _get_json("odds/multi", "super-secret-key", eventIds="1", bookmakers="Bet365")
    assert "super-secret-key" not in str(caught.value)


def test_connection_errors_do_not_include_api_key():
    error = requests.ConnectionError("failed URL containing super-secret-key")
    with patch("scripts.fetch_odds.requests.get", side_effect=error):
        with pytest.raises(RuntimeError) as caught:
            _get_json("events", "super-secret-key", sport="football")
    assert "super-secret-key" not in str(caught.value)
