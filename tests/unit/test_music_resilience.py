import threading
import time

import pytest
from fakes import FakeClock

from reveil_musical.application.music_chain import MusicFallbackChain
from reveil_musical.domain.errors import ProviderUnavailable
from reveil_musical.domain.models import Track
from reveil_musical.infrastructure.music.guards import (
    CachingMusicProvider,
    CircuitBreakerMusicProvider,
    RateLimitedMusicProvider,
)
from reveil_musical.infrastructure.music.local import DEFAULT_TRACKS, LocalFallbackMusicProvider

TRACK = Track("Clouds", "Zara Larsson", "fake")


class CountingProvider:
    def __init__(self, result=TRACK, error=None):
        self.result, self.error, self.calls = result, error, 0

    def find_track(self, query):
        self.calls += 1
        if self.error:
            raise ProviderUnavailable(self.error)
        return self.result


# --- Rate limit (iTunes ~20 req/min) ---

def test_rate_limit_refuses_the_21st_call_without_calling_the_provider():
    inner, clock = CountingProvider(), FakeClock()
    limited = RateLimitedMusicProvider(inner, clock, max_calls=20, window_seconds=60)
    for _ in range(20):
        limited.find_track("q")

    with pytest.raises(ProviderUnavailable):
        limited.find_track("q")
    assert inner.calls == 20


def test_rate_limit_window_slides_with_the_clock():
    inner, clock = CountingProvider(), FakeClock()
    limited = RateLimitedMusicProvider(inner, clock, max_calls=1, window_seconds=60)
    limited.find_track("q")
    clock.advance(60.1)

    assert limited.find_track("q") == TRACK


# --- Cache ---

def test_cache_hit_does_not_call_the_provider_again():
    inner, clock = CountingProvider(), FakeClock()
    cached = CachingMusicProvider(inner, clock, ttl_seconds=3600)

    assert cached.find_track("Clouds") == cached.find_track("clouds ") == TRACK
    assert inner.calls == 1


def test_cache_entries_expire():
    inner, clock = CountingProvider(), FakeClock()
    cached = CachingMusicProvider(inner, clock, ttl_seconds=10)
    cached.find_track("q")
    clock.advance(11)
    cached.find_track("q")

    assert inner.calls == 2


def test_failures_are_not_cached():
    inner, clock = CountingProvider(error="500"), FakeClock()
    cached = CachingMusicProvider(inner, clock, ttl_seconds=10)
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            cached.find_track("q")

    assert inner.calls == 2


def test_cache_in_front_of_rate_limit_spares_the_quota():
    inner, clock = CountingProvider(), FakeClock()
    guarded = CachingMusicProvider(RateLimitedMusicProvider(inner, clock, 1, 60), clock, 3600)

    for _ in range(5):
        assert guarded.find_track("same") == TRACK
    assert inner.calls == 1


# --- Fallback local ---

def test_local_fallback_matches_title_when_known():
    track = LocalFallbackMusicProvider(DEFAULT_TRACKS).find_track(DEFAULT_TRACKS[1].title.upper())
    assert track == DEFAULT_TRACKS[1]


def test_local_fallback_always_returns_a_track():
    assert LocalFallbackMusicProvider(DEFAULT_TRACKS).find_track("totalement inconnu") == DEFAULT_TRACKS[0]


# --- Chaîne de repli iTunes -> MusicBrainz -> local ---

def test_chain_uses_the_first_provider_when_healthy():
    first, second = CountingProvider(), CountingProvider()

    assert MusicFallbackChain({"first": first, "second": second}).resolve("q") == (TRACK, False)
    assert second.calls == 0


@pytest.mark.parametrize("failing", [CountingProvider(error="HTTP 500"), CountingProvider(error="timeout"), CountingProvider(result=None)])
def test_chain_falls_back_on_error_or_empty_result(failing):
    backup = Track("Backup", "B", "musicbrainz")

    assert MusicFallbackChain({"failing": failing, "backup": CountingProvider(result=backup)}).resolve("q") == (backup, True)


def test_chain_ends_on_local_list_when_every_remote_is_down():
    chain = MusicFallbackChain(
        {
            "itunes": CountingProvider(error="500"),
            "musicbrainz": CountingProvider(error="timeout"),
            "local": LocalFallbackMusicProvider(DEFAULT_TRACKS),
        }
    )

    assert chain.resolve("q") == (DEFAULT_TRACKS[0], True)


def test_chain_survives_an_unexpected_bug_in_a_provider(caplog):
    class Buggy:
        def find_track(self, query):
            raise AttributeError("bug dans un adapter")

    local = LocalFallbackMusicProvider(DEFAULT_TRACKS)

    assert MusicFallbackChain({"buggy": Buggy(), "local": local}).resolve("q") == (DEFAULT_TRACKS[0], True)
    assert "AttributeError" in caplog.text  # trace complète : un bug doit se voir


def test_chain_logs_which_provider_failed(caplog):
    MusicFallbackChain({"itunes": CountingProvider(error="circuit ouvert"), "next": CountingProvider()}).resolve("q")

    assert "itunes" in caplog.text and "circuit ouvert" in caplog.text


def test_chain_with_nothing_left_raises():
    with pytest.raises(ProviderUnavailable):
        MusicFallbackChain({"only": CountingProvider(error="500")}).resolve("q")


# --- Coupe-circuit ---

def breaker(inner, clock):
    return CircuitBreakerMusicProvider(inner, clock, failure_threshold=3, reset_seconds=60)


def fail_n_times(provider, n):
    for _ in range(n):
        with pytest.raises(ProviderUnavailable):
            provider.find_track("q")


def test_circuit_opens_after_consecutive_failures_and_stops_calling_the_provider():
    inner, clock = CountingProvider(error="timeout"), FakeClock()
    cb = breaker(inner, clock)
    fail_n_times(cb, 3)

    fail_n_times(cb, 5)  # circuit ouvert : on échoue tout de suite, sans attendre le timeout réseau

    assert inner.calls == 3


def test_a_success_resets_the_failure_count():
    inner, clock = CountingProvider(error="timeout"), FakeClock()
    cb = breaker(inner, clock)
    fail_n_times(cb, 2)
    inner.error = None
    cb.find_track("q")
    inner.error = "timeout"
    fail_n_times(cb, 2)

    assert inner.calls == 5  # jamais 3 échecs consécutifs : le circuit est resté fermé


def test_after_the_delay_one_trial_call_closes_the_circuit_on_success():
    inner, clock = CountingProvider(error="timeout"), FakeClock()
    cb = breaker(inner, clock)
    fail_n_times(cb, 3)
    clock.advance(60)
    inner.error = None

    assert cb.find_track("q") == TRACK
    assert cb.find_track("q") == TRACK
    assert inner.calls == 5


def test_a_failed_trial_call_reopens_the_circuit():
    inner, clock = CountingProvider(error="timeout"), FakeClock()
    cb = breaker(inner, clock)
    fail_n_times(cb, 3)
    clock.advance(60)
    fail_n_times(cb, 1)  # essai semi-ouvert, échoue

    fail_n_times(cb, 3)

    assert inner.calls == 4


# --- Concurrence : plusieurs réveils au même instant ---

class SlowLimit(int):
    """Quota dont la comparaison cède la main : ouvre la fenêtre de course entre
    « vérifier le quota » et « enregistrer l'appel », comme le ferait un vrai ordonnanceur."""

    def __le__(self, other):  # appelé pour `len(calls) >= limit`
        time.sleep(0.001)
        return int.__le__(self, other)


def test_quota_holds_under_concurrent_wake_ups():
    inner = CountingProvider()
    limited = RateLimitedMusicProvider(inner, FakeClock(), max_calls=SlowLimit(20), window_seconds=60)
    barrier = threading.Barrier(50)

    def wake():
        barrier.wait()
        try:
            limited.find_track("q")
        except ProviderUnavailable:
            pass

    threads = [threading.Thread(target=wake) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert inner.calls == 20
