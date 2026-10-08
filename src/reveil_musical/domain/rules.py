"""Règles métier pures."""
from .models import DayOfWeek, Track, UserProfile, WakeUpMessage, Weather

_WEATHER_LABELS = {
    Weather.SOLEIL: "grand soleil",
    Weather.PLUIE: "de la pluie",
    Weather.NEIGE: "de la neige",
    Weather.NUAGEUX: "un ciel nuageux",
}


def select_track_query(profile: UserProfile, weather: Weather) -> str:
    return profile.tracks_by_weather.get(weather, profile.backup_track)


def build_message(track: Track, day: DayOfWeek, weather: Weather) -> WakeUpMessage:
    day_label = day.value.lower()
    return WakeUpMessage(
        subject=f"Bon {day_label} ! C'est l'heure du réveil",
        body=(
            f"Ce {day_label}, la météo annonce {_WEATHER_LABELS[weather]}. "
            f"Votre morceau : {track.title} — {track.artist}."
        ),
    )
