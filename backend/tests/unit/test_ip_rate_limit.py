"""Unit tests for IP extraction in IP rate-limiting middleware."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import Request

from app.api.ip_rate_limit import _get_client_ip


def _build_request(*, forwarded_for: str | None, client_ip: str = "10.0.0.9") -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": (client_ip, 12345),
        "server": ("localhost", 8000),
    }
    return Request(scope)


def test_get_client_ip_ignores_forwarded_header_when_no_trusted_proxies():
    request = _build_request(forwarded_for="1.1.1.1, 2.2.2.2", client_ip="10.1.2.3")
    with patch(
        "app.api.ip_rate_limit.get_settings",
        return_value=SimpleNamespace(trusted_proxy_hops=0),
    ):
        assert _get_client_ip(request) == "10.1.2.3"


def test_get_client_ip_uses_rightmost_for_single_trusted_proxy():
    request = _build_request(forwarded_for="8.8.8.8, 203.0.113.55")
    with patch(
        "app.api.ip_rate_limit.get_settings",
        return_value=SimpleNamespace(trusted_proxy_hops=1),
    ):
        assert _get_client_ip(request) == "203.0.113.55"


def test_get_client_ip_uses_nth_from_right_for_multiple_trusted_proxies():
    request = _build_request(forwarded_for="9.9.9.9, 203.0.113.60, 172.31.0.10")
    with patch(
        "app.api.ip_rate_limit.get_settings",
        return_value=SimpleNamespace(trusted_proxy_hops=2),
    ):
        assert _get_client_ip(request) == "203.0.113.60"


def test_get_client_ip_falls_back_when_header_chain_too_short():
    request = _build_request(forwarded_for="203.0.113.7", client_ip="10.9.8.7")
    with patch(
        "app.api.ip_rate_limit.get_settings",
        return_value=SimpleNamespace(trusted_proxy_hops=3),
    ):
        assert _get_client_ip(request) == "10.9.8.7"
