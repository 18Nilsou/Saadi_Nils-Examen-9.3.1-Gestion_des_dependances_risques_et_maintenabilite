"""Décorateurs de MusicProvider : cache, coupe-circuit et limitation de débit (iTunes ~20 req/min,
MusicBrainz 1 req/s). Ils portent un état partagé entre réveils : à enregistrer en singleton
thread-safe. Chaque verrou ne protège que l'état, jamais l'appel réseau (pas de sérialisation)."""
import threading
from collections import deque

from reveil_musical.domain.errors import ProviderUnavailable, QueryRejected, QuotaExceeded
from reveil_musical.domain.models import Track
from reveil_musical.domain.ports import Clock, MusicProvider


class RateLimitedMusicProvider:
    """Fenêtre glissante. Quota atteint -> ProviderUnavailable immédiat : on bascule
    sur le fournisseur suivant au lieu d'attendre (le réveil a une heure précise)."""

    def __init__(self, inner: MusicProvider, clock: Clock, max_calls: int, window_seconds: float):
        self._inner = inner
        self._clock = clock
        self._max_calls = max_calls
        self._window = window_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def find_track(self, query: str) -> Track | None:
        with self._lock:  # vérifier puis réserver doit être atomique
            now = self._clock.now()
            while self._calls and self._calls[0] <= now - self._window:
                self._calls.popleft()
            if len(self._calls) >= self._max_calls:
                raise QuotaExceeded("quota de requêtes atteint")
            self._calls.append(now)
        return self._inner.find_track(query)


class CachingMusicProvider:
    """Cache TTL par requête (y compris les « non trouvé ») ; les pannes ne sont pas mises en cache."""

    # ponytail: cache mémoire non borné, passer à un LRU/Redis si le nombre de morceaux distincts explose
    def __init__(self, inner: MusicProvider, clock: Clock, ttl_seconds: float):
        self._inner = inner
        self._clock = clock
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[float, Track | None]] = {}
        self._lock = threading.Lock()

    def find_track(self, query: str) -> Track | None:
        key = query.strip().casefold()
        with self._lock:
            now = self._clock.now()
            hit = self._entries.get(key)
        if hit and hit[0] > now:
            return hit[1]
        track = self._inner.find_track(query)
        with self._lock:
            self._entries[key] = (now + self._ttl, track)
        return track


class CircuitBreakerMusicProvider:
    """Coupe-circuit (J1 : SPOF). Après `failure_threshold` échecs consécutifs, le circuit
    s'ouvre : ProviderUnavailable immédiat, sans appel réseau, donc sans attendre un timeout
    à chaque réveil. Après `reset_seconds`, un seul appel d'essai (semi-ouvert) :
    succès -> fermé, échec -> ré-ouvert. Un refus du quota placé derrière (QuotaExceeded) ou
    d'une requête précise (QueryRejected, HTTP 4xx) n'est pas un échec : sinon une source saine
    serait coupée 60 s par notre propre limite ou par un titre exotique."""

    def __init__(self, inner: MusicProvider, clock: Clock, failure_threshold: int, reset_seconds: float):
        self._inner = inner
        self._clock = clock
        self._threshold = failure_threshold
        self._reset = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def find_track(self, query: str) -> Track | None:
        with self._lock:
            if self._opened_at is not None:
                now = self._clock.now()
                if now - self._opened_at < self._reset:
                    raise ProviderUnavailable("circuit ouvert")
                # semi-ouvert : ce thread fait l'essai, le circuit reste ouvert pour les autres
                self._opened_at, self._failures = now, self._threshold - 1
        try:
            track = self._inner.find_track(query)
        except (QuotaExceeded, QueryRejected):
            raise  # notre limite ou notre requête, pas une panne du fournisseur : ne compte pas
        except ProviderUnavailable:
            with self._lock:
                self._failures += 1
                if self._failures >= self._threshold:
                    self._opened_at = self._clock.now()
            raise
        with self._lock:
            self._failures, self._opened_at = 0, None
        return track
