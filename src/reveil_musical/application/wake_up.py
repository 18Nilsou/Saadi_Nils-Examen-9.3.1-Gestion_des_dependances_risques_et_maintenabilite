from typing import Protocol

from reveil_musical.domain.models import Channel, DayOfWeek, Track, UserProfile, WakeUpMessage, WakeUpResult, Weather
from reveil_musical.domain.ports import UserPreferencesRepository
from reveil_musical.domain.rules import build_message, select_track_query


class TrackResolver(Protocol):  # tenu par MusicFallbackChain
    def resolve(self, query: str) -> tuple[Track, bool]:
        """(morceau, dégradé) ; ne lève que si aucune source, locale comprise, ne répond."""


class Notifier(Protocol):  # tenu par NotificationDispatcher
    def dispatch(self, profile: UserProfile, message: WakeUpMessage) -> tuple[Channel, bool]:
        """(canal utilisé, dégradé)."""


class WakeUpUseCase:
    """Point d'entrée du TP, appelé à l'heure du réveil. Ne connaît que des abstractions
    reçues par constructeur : la résilience vit dans la chaîne musicale et le dispatcher."""

    def __init__(self, users: UserPreferencesRepository, music: TrackResolver, notifier: Notifier):
        self._users = users
        self._music = music
        self._notifier = notifier

    def execute(self, user_id: str, day: DayOfWeek, weather: Weather) -> WakeUpResult:
        profile = self._users.get(user_id)
        track, music_degraded = self._music.resolve(select_track_query(profile, day, weather))
        channel, channel_degraded = self._notifier.dispatch(profile, build_message(track, day, weather))
        return WakeUpResult(track=track, channel=channel, degraded=music_degraded or channel_degraded)
