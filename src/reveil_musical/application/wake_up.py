from reveil_musical.domain.models import DayOfWeek, WakeUpResult, Weather
from reveil_musical.domain.ports import UserPreferencesRepository
from reveil_musical.domain.rules import build_message, select_track_query

from .music_chain import MusicFallbackChain
from .notifier import NotificationDispatcher


class WakeUpUseCase:
    """Point d'entrée du TP, appelé à l'heure du réveil. Ne connaît que des abstractions
    reçues par constructeur : la résilience vit dans la chaîne musicale et le dispatcher."""

    def __init__(self, users: UserPreferencesRepository, music: MusicFallbackChain, notifier: NotificationDispatcher):
        self._users = users
        self._music = music
        self._notifier = notifier

    def execute(self, user_id: str, day: DayOfWeek, weather: Weather) -> WakeUpResult:
        profile = self._users.get(user_id)
        track, music_degraded = self._music.resolve(select_track_query(profile, weather))
        channel, channel_degraded = self._notifier.dispatch(profile, build_message(track, day, weather))
        return WakeUpResult(track=track, channel=channel, degraded=music_degraded or channel_degraded)
