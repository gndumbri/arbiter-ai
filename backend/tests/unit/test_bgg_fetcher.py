"""Unit tests for BGG catalog metadata ingestion helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from app.services.catalog.bgg_fetcher import _fetch_ranked_list


def _mock_response(body: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = body
    return response


@patch("app.services.catalog.bgg_fetcher.requests.get")
def test_fetch_ranked_list_parses_primary_links(mock_get: MagicMock) -> None:
    html = """
    <a href="/boardgame/12345/catan" class='primary'>Catan</a>
    <a href="/boardgame/67890/brass-birmingham" class='primary'>Brass: Birmingham</a>
    """
    mock_get.return_value = _mock_response(html)

    games = _fetch_ranked_list(limit=2)

    assert len(games) == 2
    assert games[0]["bgg_id"] == "12345"
    assert games[0]["name"] == "Catan"
    assert games[0]["rank"] == 1
    assert games[1]["bgg_id"] == "67890"
    assert games[1]["name"] == "Brass: Birmingham"
    assert games[1]["rank"] == 2


@patch("app.services.catalog.bgg_fetcher.requests.get")
def test_fetch_ranked_list_handles_request_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.RequestException("boom")

    games = _fetch_ranked_list(limit=10)

    assert games == []
