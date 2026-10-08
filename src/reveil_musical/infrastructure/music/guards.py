"""Décorateurs de MusicProvider : cache et limitation de débit (iTunes ~20 req/min,
MusicBrainz 1 req/s). Ils portent un état partagé : à enregistrer en Singleton."""
from collections import deque

from reveil_musical.domain.errors import ProviderUnavailable
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

    def find_track(self, query: str) -> Track | None:
        now = self._clock.now()
        while self._calls and self._calls[0] <= now - self._window:
            self._calls.popleft()
        if len(self._calls) >= self._max_calls:
            raise ProviderUnavailable("quota de requêtes atteint")
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

    def find_track(self, query: str) -> Track | None:
        key = query.strip().casefold()
        now = self._clock.now()
        hit = self._entries.get(key)
        if hit and hit[0] > now:
            return hit[1]
        track = self._inner.find_track(query)
        self._entries[key] = (now + self._ttl, track)
        return track


class CircuitBreakerMusicProvider:
    """Coupe-circuit (J1 : SPOF). Après `failure_threshold` échecs consécutifs, le circuit
    s'ouvre : ProviderUnavailable immédiat, sans appel réseau, donc sans attendre un timeout
    à chaque réveil. Après `reset_seconds`, un appel d'essai : succès -> fermé, échec -> ré-ouvert."""

    def __init__(self, inner: MusicProvider, clock: Clock, failure_threshold: int, reset_seconds: float):
        self._inner = inner
        self._clock = clock
        self._threshold = failure_threshold
        self._reset = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def find_track(self, query: str) -> Track | None:
        if self._opened_at is not None:
            if self._clock.now() - self._opened_at < self._reset:
                raise ProviderUnavailable("circuit ouvert")
            self._failures = self._threshold - 1  # semi-ouvert : un seul essai
        try:
            track = self._inner.find_track(query)
        except ProviderUnavailable:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = self._clock.now()
            raise
        self._failures, self._opened_at = 0, None
        return track
