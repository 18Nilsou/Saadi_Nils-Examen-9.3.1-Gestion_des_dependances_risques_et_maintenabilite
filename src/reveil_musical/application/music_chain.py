import logging
from collections.abc import Mapping

from reveil_musical.domain.errors import ProviderUnavailable
from reveil_musical.domain.models import Track
from reveil_musical.domain.ports import MusicProvider

_log = logging.getLogger(__name__)


class MusicFallbackChain:
    """Chaîne de responsabilité : essaie chaque fournisseur dans l'ordre injecté (nom -> fournisseur,
    ordre d'insertion) et passe au suivant sur panne ou résultat vide. L'ordre se décide dans
    le conteneur, pas ici. Point unique par où passent toutes les sources : c'est ici qu'on
    garantit qu'aucune panne musicale, même imprévue, n'empêche le réveil."""

    def __init__(self, providers: Mapping[str, MusicProvider]):
        self._providers = providers

    def resolve(self, query: str) -> tuple[Track, bool]:
        """Renvoie (morceau, dégradé) ; dégradé = un autre fournisseur que le premier a répondu."""
        for rank, (name, provider) in enumerate(self._providers.items()):
            try:
                track = provider.find_track(query)
            except Exception as e:  # panne prévue (ProviderUnavailable) ou bug d'adapter : on passe au suivant
                _log.warning(
                    "fournisseur %s indisponible : %s", name, e, exc_info=not isinstance(e, ProviderUnavailable)
                )
                continue
            if track is not None:
                return track, rank > 0
        raise ProviderUnavailable(f"aucun fournisseur n'a de morceau pour {query!r}")
