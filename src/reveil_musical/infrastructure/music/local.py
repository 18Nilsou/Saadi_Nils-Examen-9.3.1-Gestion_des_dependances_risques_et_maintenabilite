"""Fallback local codé en dur : utilisé quand aucun fournisseur n'est disponible."""
from collections.abc import Sequence

from reveil_musical.domain.models import Track

DEFAULT_TRACKS = (
    Track("Wake Me Up", "Avicii", "local"),
    Track("Here Comes the Sun", "The Beatles", "local"),
    Track("Good Morning Starshine", "Oliver", "local"),
    Track("Mr. Blue Sky", "Electric Light Orchestra", "local"),
)


class LocalFallbackMusicProvider:
    def __init__(self, tracks: Sequence[Track]):
        self._tracks = tracks

    def find_track(self, query: str) -> Track:
        wanted = query.strip().casefold()
        return next((t for t in self._tracks if t.title.casefold() == wanted), self._tracks[0])
