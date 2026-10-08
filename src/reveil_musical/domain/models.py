"""Modèles métier purs : aucun détail technique, aucun champ propre à un fournisseur."""
from collections.abc import Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    tracks_by_weather: Mapping[Weather, str]
    backup_track: str
    preferred_channel: Channel
    contacts: Mapping[Channel, str]


@dataclass(frozen=True)
class WakeUpMessage:
    subject: str
    body: str


@dataclass(frozen=True)
class WakeUpResult:
    track: Track
    channel: Channel
    degraded: bool
