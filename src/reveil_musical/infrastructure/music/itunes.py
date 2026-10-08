"""Adapter iTunes Search API : le JSON iTunes (trackName, trackViewUrl…) ne sort jamais d'ici."""
from reveil_musical.domain.errors import ProviderUnavailable
from reveil_musical.domain.models import Track

from ..http import JsonHttpClient


class ITunesMusicProvider:
    def __init__(self, http: JsonHttpClient, base_url: str):
        self._http = http
        self._base_url = base_url

    def find_track(self, query: str) -> Track | None:
        data = self._http.get_json(f"{self._base_url}/search", {"term": query, "media": "music", "limit": 5})
        try:
            results = data["results"]
            if not results:
                return None
            return Track(title=results[0]["trackName"], artist=results[0]["artistName"], source="itunes")
        except (KeyError, TypeError, IndexError, ValueError) as e:
            raise ProviderUnavailable(f"itunes: réponse inattendue ({e!r})") from e
