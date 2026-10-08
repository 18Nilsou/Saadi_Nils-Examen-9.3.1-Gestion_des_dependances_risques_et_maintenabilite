import logging
from collections.abc import Sequence

from reveil_musical.domain.errors import ProviderUnavailable
from reveil_musical.domain.models import Track
from reveil_musical.domain.ports import MusicProvider

_log = logging.getLogger(__name__)


class MusicFallbackChain:
    """Chaîne de responsabilité : essaie chaque fournisseur dans l'ordre injecté et passe
    au suivant sur panne ou résultat vide. L'ordre se décide dans le conteneur, pas ici."""

    def __init__(self, providers: Sequence[MusicProvider]):
        self._providers = providers

    def resolve(self, query: str) -> tuple[Track, bool]:
        """Renvoie (morceau, dégradé) ; dégradé = un autre fournisseur que le premier a répondu."""
        for rank, provider in enumerate(self._providers):
            try:
                track = provider.find_track(query)
            except ProviderUnavailable as e:
                _log.warning("fournisseur %s indisponible : %s", type(provider).__name__, e)
                continue
            if track is not None:
                return track, rank > 0
        raise ProviderUnavailable(f"aucun fournisseur n'a de morceau pour {query!r}")
