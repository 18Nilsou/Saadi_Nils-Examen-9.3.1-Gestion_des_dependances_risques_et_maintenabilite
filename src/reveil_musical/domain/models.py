"""Modèles métier purs : aucun détail technique, aucun champ propre à un fournisseur."""
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class Weather(StrEnum):
    SOLEIL = "SOLEIL"
    PLUIE = "PLUIE"
    NEIGE = "NEIGE"
    NUAGEUX = "NUAGEUX"


class DayOfWeek(StrEnum):
    LUNDI = "LUNDI"
    MARDI = "MARDI"
    MERCREDI = "MERCREDI"
    JEUDI = "JEUDI"
    VENDREDI = "VENDREDI"
    SAMEDI = "SAMEDI"
    DIMANCHE = "DIMANCHE"


class Channel(StrEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    LOG = "LOG"  # dernier recours, jamais choisi par l'utilisateur


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    source: str

    def __post_init__(self):
        for name in ("title", "artist"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Track.{name} doit être une chaîne non vide, reçu {value!r}")


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    tracks_by_weather: Mapping[Weather, str]
    backup_track: str
    preferred_channel: Channel
    contacts: Mapping[Channel, str]
    # Surcharge facultative : un morceau pour un couple (jour, météo) précis.
    tracks_by_day: Mapping[tuple[DayOfWeek, Weather], str] = field(default_factory=dict)


@dataclass(frozen=True)
class WakeUpMessage:
    subject: str
    body: str


@dataclass(frozen=True)
class WakeUpResult:
    track: Track
    channel: Channel
    degraded: bool
