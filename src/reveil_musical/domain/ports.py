"""Ports (boundaries) : ce dont le métier a besoin, sans savoir qui le fournit."""
from typing import Protocol

from .models import Track, UserProfile, WakeUpMessage


class MusicProvider(Protocol):
    def find_track(self, query: str) -> Track | None:
        """None si rien trouvé ; lève ProviderUnavailable si le fournisseur est indisponible."""


class NotificationSender(Protocol):
    def send(self, contact: str, message: WakeUpMessage) -> None:
        """Lève NotificationFailed si l'envoi échoue."""


class UserPreferencesRepository(Protocol):
    def get(self, user_id: str) -> UserProfile:
        """Lève UnknownUser si l'utilisateur n'existe pas."""


class Clock(Protocol):
    def now(self) -> float:
        """Secondes monotones."""
