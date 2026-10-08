"""Composition root : le SEUL endroit qui connaît les classes concrètes et les assemble.
Choisir/réordonner les sources musicales = variable REVEIL_MUSIC_PROVIDERS, sans toucher au code.
Ajouter une nouvelle source ou un nouveau canal = un adapter + une ligne ici, rien d'autre.

Durées de vie :
- Singleton (ThreadSafeSingleton : providers.Singleton ne l'est pas, et deux réveils
  simultanés ne doivent pas créer deux quotas) : composants sans état par réveil, ou dont l'état DOIT être partagé
  (cache, compteur de quota). Ils ne dépendent que d'autres singletons ou de la config
  -> pas de dépendance captive (vérifié par test).
- Factory (transient) : orchestrations applicatives, légères et sans état.
- Scoped : inutile ici, aucun état « par réveil » à partager.
"""
import os
from collections.abc import Mapping

from dependency_injector import containers, providers

from .application.music_chain import MusicFallbackChain
from .application.notifier import NotificationDispatcher
from .application.wake_up import WakeUpUseCase
from .domain.models import Channel
from .infrastructure.clock import SystemClock
from .infrastructure.http import JsonHttpClient
from .infrastructure.music.guards import (
    CachingMusicProvider,
    CircuitBreakerMusicProvider,
    RateLimitedMusicProvider,
)
from .infrastructure.music.itunes import ITunesMusicProvider
from .infrastructure.music.local import DEFAULT_TRACKS, LocalFallbackMusicProvider
from .infrastructure.music.musicbrainz import MusicBrainzMusicProvider
from .infrastructure.notifications.adapters import (
    EmailNotificationAdapter,
    LogNotificationSender,
    PushNotificationAdapter,
    SmsNotificationAdapter,
)
from .infrastructure.notifications.clients import EmailClient, PushNotifier, SmsGateway
from .infrastructure.users.in_memory import DEMO_PROFILES, InMemoryUserPreferencesRepository

# Dépendances implicites documentées : chaque clé est surchargeable par REVEIL_<CLE>.
DEFAULTS = {
    "itunes_url": "https://itunes.apple.com",
    "music_providers": "itunes,musicbrainz",
    "musicbrainz_url": "https://musicbrainz.org",
    "musicbrainz_user_agent": "ReveilMusical/0.1 ( https://github.com/18Nilsou/Saadi_Nils-Examen-9.3.1-Gestion_des_dependances_risques_et_maintenabilite )",
    "http_timeout": 3.0,
    "cache_ttl": 86400.0,
}


def _names(order: str) -> list[str]:
    return [name.strip() for name in order.split(",") if name.strip()]


def _ordered_providers(order: str, remote: Mapping, local) -> list:
    """Sources distantes dans l'ordre configuré, la liste locale toujours en dernier."""
    return [remote[name] for name in _names(order)] + [local]


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    clock = providers.ThreadSafeSingleton(SystemClock)
    http = providers.ThreadSafeSingleton(JsonHttpClient, timeout=config.http_timeout)

    # --- Musique : cache -> coupe-circuit -> quota -> adapter, pour chaque fournisseur distant ---
    itunes = providers.ThreadSafeSingleton(
        CachingMusicProvider,
        inner=providers.ThreadSafeSingleton(
            CircuitBreakerMusicProvider,
            inner=providers.ThreadSafeSingleton(
                RateLimitedMusicProvider,
                inner=providers.ThreadSafeSingleton(ITunesMusicProvider, http=http, base_url=config.itunes_url),
                clock=clock,
                max_calls=20,
                window_seconds=60,
            ),
            clock=clock,
            failure_threshold=3,
            reset_seconds=60,
        ),
        clock=clock,
        ttl_seconds=config.cache_ttl,
    )
    musicbrainz = providers.ThreadSafeSingleton(
        CachingMusicProvider,
        inner=providers.ThreadSafeSingleton(
            CircuitBreakerMusicProvider,
            inner=providers.ThreadSafeSingleton(
                RateLimitedMusicProvider,
                inner=providers.ThreadSafeSingleton(
                    MusicBrainzMusicProvider,
                    http=http,
                    base_url=config.musicbrainz_url,
                    user_agent=config.musicbrainz_user_agent,
                ),
                clock=clock,
                max_calls=1,
                window_seconds=1,
            ),
            clock=clock,
            failure_threshold=3,
            reset_seconds=60,
        ),
        clock=clock,
        ttl_seconds=config.cache_ttl,
    )
    local_music = providers.ThreadSafeSingleton(LocalFallbackMusicProvider, tracks=providers.Object(DEFAULT_TRACKS))

    # Sources distantes interchangeables : leur ordre vient de REVEIL_MUSIC_PROVIDERS.
    remote_music = providers.Dict(itunes=itunes, musicbrainz=musicbrainz)
    music_chain = providers.Factory(
        MusicFallbackChain,
        providers=providers.Callable(_ordered_providers, config.music_providers, remote_music, local_music),
    )

    # --- Notifications : un faux SDK + son adapter par canal ---
    email = providers.ThreadSafeSingleton(EmailNotificationAdapter, client=providers.ThreadSafeSingleton(EmailClient))
    sms = providers.ThreadSafeSingleton(SmsNotificationAdapter, gateway=providers.ThreadSafeSingleton(SmsGateway))
    push = providers.ThreadSafeSingleton(PushNotificationAdapter, notifier=providers.ThreadSafeSingleton(PushNotifier))
    last_resort = providers.ThreadSafeSingleton(LogNotificationSender)

    notifier = providers.Factory(
        NotificationDispatcher,
        senders=providers.Dict({Channel.EMAIL: email, Channel.SMS: sms, Channel.PUSH: push}),
        last_resort=last_resort,
    )

    # --- Utilisateurs (mock du service interne) ---
    users = providers.ThreadSafeSingleton(InMemoryUserPreferencesRepository, profiles=providers.Object(DEMO_PROFILES))

    wake_up_use_case = providers.Factory(WakeUpUseCase, users=users, music=music_chain, notifier=notifier)


def create_container(env: Mapping[str, str] = os.environ) -> Container:
    container = Container()
    container.config.from_dict(
        {key: type(default)(env.get(f"REVEIL_{key.upper()}", default)) for key, default in DEFAULTS.items()}
    )
    unknown = set(_names(container.config.music_providers())) - set(container.remote_music.kwargs)
    if unknown:  # échouer au démarrage plutôt qu'à l'heure du réveil
        raise ValueError(f"REVEIL_MUSIC_PROVIDERS : fournisseur(s) inconnu(s) {sorted(unknown)}")
    return container
