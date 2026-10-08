"""Contrat du client HTTP réel, contre un serveur local (aucun accès Internet)."""
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from reveil_musical.domain.errors import ProviderUnavailable, QueryRejected
from reveil_musical.infrastructure.http import JsonHttpClient


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/slow"):
            time.sleep(0.5)
        status, body = {
            "/ok": (200, b'{"ua": "%s"}' % self.headers["User-Agent"].encode()),
            "/boom": (500, b"error"),
            "/notjson": (200, b"<html>"),
            "/bad": (400, b"bad query"),
            "/throttled": (403, b"forbidden"),
            "/toomany": (429, b"slow down"),
        }.get(self.path.split("?")[0], (200, b"{}"))
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def base_url():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_returns_parsed_json_and_sends_headers(base_url):
    data = JsonHttpClient(timeout=2).get_json(f"{base_url}/ok", {"q": "a b"}, {"User-Agent": "Test/1.0"})
    assert data == {"ua": "Test/1.0"}


@pytest.mark.parametrize("path", ["/boom", "/notjson", "/slow"])
def test_errors_and_timeouts_become_provider_unavailable(base_url, path):
    with pytest.raises(ProviderUnavailable):
        JsonHttpClient(timeout=0.2).get_json(f"{base_url}{path}")


def test_unreachable_host_becomes_provider_unavailable():
    with pytest.raises(ProviderUnavailable):
        JsonHttpClient(timeout=0.5).get_json("http://127.0.0.1:9/nothing")


def test_a_4xx_rejects_the_query_not_the_provider(base_url):
    with pytest.raises(QueryRejected):
        JsonHttpClient(timeout=2).get_json(f"{base_url}/bad")


@pytest.mark.parametrize("path", ["/throttled", "/toomany", "/boom"])
def test_throttling_and_5xx_remain_outages(base_url, path):
    with pytest.raises(ProviderUnavailable) as raised:
        JsonHttpClient(timeout=2).get_json(f"{base_url}{path}")
    assert not isinstance(raised.value, QueryRejected)
