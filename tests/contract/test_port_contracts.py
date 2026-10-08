"""Tests de contrat par abstraction (J2) : la MÊME suite s'applique à TOUTES les implémentations
d'un port. Une nouvelle source musicale ou un nouveau canal s'ajoute ici en une ligne et
hérite de tout le contrat ; s'il ne le respecte pas, la chaîne de repli n'est plus garantie."""
import pytest
from fakes import FakeClock, FakeHttp, SdkSpy, load_fixture

from reveil_musical.domain.errors import NotificationFailed, ProviderUnavailable
from reveil_musical.domain.models import Track, WakeUpMessage
from reveil_musical.infrastructure.music.guards import (
    CachingMusicProvider,
    CircuitBreakerMusicProvider,
    RateLimitedMusicProvider,
)
from reveil_musical.infrastructure.music.itunes import ITunesMusicProvider
from reveil_musical.infrastructure.music.local import DEFAULT_TRACKS, LocalFallbackMusicProvider
from reveil_musical.infrastructure.music.musicbrainz import MusicBrainzMusicProvider
from reveil_musical.infrastructure.notifications.adapters import (
    EmailNotificationAdapter,
    LogNotificationSender,
    PushNotificationAdapter,
    SmsNotificationAdapter,
)
from reveil_musical.infrastructure.notifications.clients import EmailDeliveryError, PushRejected, SmsGatewayError

# --- MusicProvider : find_track(query) -> Track | None, ne lève que ProviderUnavailable ---

# Comportement du « vrai » fournisseur simulé selon le mode : trouvé / vide / en panne.
ITUNES_HTTP = {
    "found": lambda: FakeHttp(load_fixture("itunes_search.json")),
    "empty": lambda: FakeHttp({"resultCount": 0, "results": []}),
    "down": lambda: FakeHttp(error="HTTP 500"),
}
MUSICBRAINZ_HTTP = {
    "found": lambda: FakeHttp(load_fixture("musicbrainz_recording.json")),
    "empty": lambda: FakeHttp({"recordings": []}),
    "down": lambda: FakeHttp(error="timeout"),
}


def itunes(mode):
    return ITunesMusicProvider(ITUNES_HTTP[mode](), "https://itunes.test")


def musicbrainz(mode):
    return MusicBrainzMusicProvider(MUSICBRAINZ_HTTP[mode](), "https://mb.test", "Test/1.0 (test)")


def local(mode):
    return LocalFallbackMusicProvider(DEFAULT_TRACKS) if mode == "found" else None  # ne tombe jamais


def cached(mode):
    return CachingMusicProvider(itunes(mode), FakeClock(), ttl_seconds=60)


def rate_limited(mode):
    return RateLimitedMusicProvider(itunes(mode), FakeClock(), max_calls=5, window_seconds=60)


def circuit_breaker(mode):
    return CircuitBreakerMusicProvider(musicbrainz(mode), FakeClock(), failure_threshold=3, reset_seconds=60)


MUSIC_PROVIDERS = [itunes, musicbrainz, local, cached, rate_limited, circuit_breaker]


def build(factory, mode):
    provider = factory(mode)
    if provider is None:
        pytest.skip(f"{factory.__name__} n'a pas de mode « {mode} »")
    return provider


@pytest.mark.parametrize("factory", MUSIC_PROVIDERS, ids=lambda f: f.__name__)
def test_music_provider_returns_a_domain_track(factory):
    track = build(factory, "found").find_track("Here Comes the Sun")

    assert type(track) is Track
    assert track.title and track.artist and track.source


@pytest.mark.parametrize("factory", MUSIC_PROVIDERS, ids=lambda f: f.__name__)
def test_music_provider_returns_none_when_nothing_matches(factory):
    assert build(factory, "empty").find_track("zzz-inconnu") is None


@pytest.mark.parametrize("factory", MUSIC_PROVIDERS, ids=lambda f: f.__name__)
def test_music_provider_only_signals_outages_with_provider_unavailable(factory):
    with pytest.raises(ProviderUnavailable):
        build(factory, "down").find_track("x")


# --- NotificationSender : send(contact, message) -> None, ne lève que NotificationFailed ---

MESSAGE = WakeUpMessage(subject="Bon lundi !", body="Votre morceau : Clouds — Zara Larsson.")

SENDERS = {
    "email": (EmailNotificationAdapter, EmailDeliveryError("smtp down")),
    "sms": (SmsNotificationAdapter, SmsGatewayError("quota")),
    "push": (PushNotificationAdapter, PushRejected("bad token")),
}


@pytest.mark.parametrize("name", [*SENDERS, "log"])
def test_sender_delivers_and_returns_nothing(name):
    sender = LogNotificationSender() if name == "log" else SENDERS[name][0](SdkSpy())

    assert sender.send("contact", MESSAGE) is None


@pytest.mark.parametrize("name", SENDERS)
def test_sender_translates_its_sdk_error_into_notification_failed(name):
    adapter_cls, sdk_error = SENDERS[name]

    with pytest.raises(NotificationFailed):
        adapter_cls(SdkSpy(sdk_error)).send("contact", MESSAGE)
