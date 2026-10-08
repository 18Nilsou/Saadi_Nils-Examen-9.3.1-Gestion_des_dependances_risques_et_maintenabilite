"""Adapter MusicBrainz : exige un User-Agent identifiable (sinon requête rejetée)."""
from reveil_musical.domain.errors import ProviderUnavailable
from reveil_musical.domain.models import Track

from ..http import JsonHttpClient


class MusicBrainzMusicProvider:
    def __init__(self, http: JsonHttpClient, base_url: str, user_agent: str):
        self._http = http
        self._base_url = base_url
        self._headers = {"User-Agent": user_agent}

    def find_track(self, query: str) -> Track | None:
        data = self._http.get_json(
            f"{self._base_url}/ws/2/recording", {"query": query, "fmt": "json"}, self._headers
        )
        try:
            recordings = data["recordings"]
            if not recordings:
                return None
            first = recordings[0]
            return Track(title=first["title"], artist=first["artist-credit"][0]["name"], source="musicbrainz")
        except (KeyError, TypeError, IndexError, ValueError) as e:
            raise ProviderUnavailable(f"musicbrainz: réponse inattendue ({e!r})") from e
