"""Composition root : le SEUL endroit qui connaît les classes concrètes et les assemble.
Changer de fournisseur ou de canal = modifier ce fichier, rien d'autre.

Durées de vie :
- Singleton : composants sans état par réveil, ou dont l'état DOIT être partagé
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
from .infrastructure.music.guards import CachingMusicProvider, RateLimitedMusicProvider
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
    "musicbrainz_url": "https://musicbrainz.org",
    "musicbrainz_user_agent": "ReveilMusical/0.1 (nils.saadi@gmail.com)",
    "http_timeout": 3.0,
    "cache_ttl": 86400.0,
}


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    clock = providers.Singleton(SystemClock)
    http = providers.Singleton(JsonHttpClient, timeout=config.http_timeout)

    # --- Musique : cache -> quota -> adapter, pour chaque fournisseur distant ---
    itunes = providers.Singleton(
        CachingMusicProvider,
        inner=providers.Singleton(
            RateLimitedMusicProvider,
            inner=providers.Singleton(ITunesMusicProvider, http=http, base_url=config.itunes_url),
            clock=clock,
            max_calls=20,
            window_seconds=60,
        ),
        clock=clock,
        ttl_seconds=config.cache_ttl,
    )
    musicbrainz = providers.Singleton(
        CachingMusicProvider,
        inner=providers.Singleton(
            RateLimitedMusicProvider,
            inner=providers.Singleton(
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
        ttl_seconds=config.cache_ttl,
    )
    local_music = providers.Singleton(LocalFallbackMusicProvider, tracks=providers.Object(DEFAULT_TRACKS))

    music_chain = providers.Factory(
        MusicFallbackChain, providers=providers.List(itunes, musicbrainz, local_music)
    )

    # --- Notifications : un faux SDK + son adapter par canal ---
    email = providers.Singleton(EmailNotificationAdapter, client=providers.Singleton(EmailClient))
    sms = providers.Singleton(SmsNotificationAdapter, gateway=providers.Singleton(SmsGateway))
    push = providers.Singleton(PushNotificationAdapter, notifier=providers.Singleton(PushNotifier))
    last_resort = providers.Singleton(LogNotificationSender)

    notifier = providers.Factory(
        NotificationDispatcher,
        senders=providers.Dict({Channel.EMAIL: email, Channel.SMS: sms, Channel.PUSH: push}),
        last_resort=last_resort,
    )

    # --- Utilisateurs (mock du service interne) ---
    users = providers.Singleton(InMemoryUserPreferencesRepository, profiles=providers.Object(DEMO_PROFILES))

    wake_up_use_case = providers.Factory(WakeUpUseCase, users=users, music=music_chain, notifier=notifier)


def create_container(env: Mapping[str, str] = os.environ) -> Container:
    container = Container()
    container.config.from_dict(
        {key: type(default)(env.get(f"REVEIL_{key.upper()}", default)) for key, default in DEFAULTS.items()}
    )
    return container
