"""Mock du service interne de préférences utilisateur (un fournisseur comme un autre)."""
from collections.abc import Iterable

from reveil_musical.domain.errors import UnknownUser
from reveil_musical.domain.models import Channel, DayOfWeek, UserProfile, Weather

DEMO_PROFILES = (
    UserProfile(
        user_id="u1",
        tracks_by_weather={
            Weather.SOLEIL: "Here Comes the Sun",
            Weather.PLUIE: "Riders on the Storm",
            Weather.NEIGE: "Let It Snow",
            Weather.NUAGEUX: "Clouds",
        },
        backup_track="Wake Me Up",
        preferred_channel=Channel.EMAIL,
        contacts={Channel.EMAIL: "alice@example.com", Channel.SMS: "+33600000001"},
        tracks_by_day={(DayOfWeek.SAMEDI, Weather.SOLEIL): "Saturday in the Park"},
    ),
    UserProfile(
        user_id="u2",
        tracks_by_weather={Weather.SOLEIL: "Walking on Sunshine", Weather.PLUIE: "Purple Rain"},
        backup_track="Good Morning Starshine",  # utilisé pour NEIGE / NUAGEUX
        preferred_channel=Channel.SMS,
        contacts={Channel.SMS: "+33600000002"},
    ),
    UserProfile(
        user_id="u3",
        tracks_by_weather={w: "Mr. Blue Sky" for w in Weather},
        backup_track="Mr. Blue Sky",
        preferred_channel=Channel.PUSH,
        contacts={Channel.PUSH: "device-token-u3", Channel.EMAIL: "carol@example.com"},
    ),
)


class InMemoryUserPreferencesRepository:
    def __init__(self, profiles: Iterable[UserProfile]):
        self._profiles = {p.user_id: p for p in profiles}

    def get(self, user_id: str) -> UserProfile:
        try:
            return self._profiles[user_id]
        except KeyError:
            raise UnknownUser(user_id) from None
