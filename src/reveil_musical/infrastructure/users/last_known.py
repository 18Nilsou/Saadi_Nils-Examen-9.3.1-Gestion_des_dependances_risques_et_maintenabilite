"""Décorateur du service utilisateurs (J1 : SPOF). Service injoignable -> dernier profil connu :
un réveil avec le profil de la veille vaut mieux qu'un silence."""
import dataclasses
import logging
import shelve
import threading
from collections.abc import MutableMapping

from reveil_musical.domain.errors import UnknownUser
from reveil_musical.domain.models import UserProfile
from reveil_musical.domain.ports import UserPreferencesRepository

_log = logging.getLogger(__name__)


def open_profile_store(path: str) -> MutableMapping[str, UserProfile]:
    """Fichier (shelve) pour survivre d'une tournée à l'autre ; sans chemin, mémoire seule.
    Le fichier ne doit être inscriptible que par le service (shelve désérialise via pickle)."""
    return shelve.open(path) if path else {}


def _rebuild(stored: UserProfile) -> UserProfile:
    """pickle restaure l'objet sans passer par __init__, avec le schéma du jour de l'écriture.
    On le repasse par le constructeur : un champ ajouté depuis prend sa valeur par défaut, un champ
    retiré est ignoré, un champ obligatoire manquant lève (profil inutilisable)."""
    known = {f.name for f in dataclasses.fields(UserProfile)}
    return UserProfile(**{k: v for k, v in vars(stored).items() if k in known})


class LastKnownUserPreferencesRepository:
    def __init__(self, inner: UserPreferencesRepository, store: MutableMapping[str, UserProfile]):
        self._inner = inner
        self._store = store
        self._lock = threading.Lock()  # shelve n'est pas thread-safe

    def get(self, user_id: str) -> UserProfile:
        try:
            profile = self._inner.get(user_id)
        except UnknownUser:
            with self._lock:
                self._store.pop(user_id, None)  # compte supprimé : on n'en garde rien
            raise
        except Exception as outage:
            try:
                with self._lock:
                    profile = _rebuild(self._store[user_id])
            except Exception:  # absent, illisible ou d'un schéma incompatible : pas de secours
                raise outage from None
            _log.warning("service utilisateurs injoignable : dernier profil connu pour %s", user_id, exc_info=True)
            return profile
        try:
            with self._lock:
                self._store[user_id] = profile
        except Exception:  # disque plein, fichier verrouillé… : le réveil passe quand même
            _log.warning("profil de %s non mémorisé", user_id, exc_info=True)
        return profile
