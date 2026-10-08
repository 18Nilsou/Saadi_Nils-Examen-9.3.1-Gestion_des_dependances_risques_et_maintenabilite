"""Fakes partagés : ils se branchent sur les seams (ports) à la place des vrais composants."""
import json
from pathlib import Path

from reveil_musical.domain.errors import ProviderUnavailable

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class FakeHttp:
    """Remplace JsonHttpClient : renvoie une réponse préparée ou simule une panne."""

    def __init__(self, response: dict | None = None, error: str | None = None):
        self.response = response
        self.error = error
        self.calls = []

    def get_json(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if self.error:
            raise ProviderUnavailable(self.error)
        return self.response


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.t = start

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds
