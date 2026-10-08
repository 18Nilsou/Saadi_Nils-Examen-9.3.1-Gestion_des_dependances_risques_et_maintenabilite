import pytest

from reveil_musical.domain.models import Channel, DayOfWeek, Track, UserProfile, Weather
from reveil_musical.domain.rules import build_message, select_track_query

PROFILE = UserProfile(
    user_id="u1",
    tracks_by_weather={Weather.SOLEIL: "Here Comes the Sun", Weather.PLUIE: "Riders on the Storm"},
    backup_track="Wake Me Up",
    preferred_channel=Channel.EMAIL,
    contacts={Channel.EMAIL: "u1@example.com"},
    tracks_by_day={(DayOfWeek.SAMEDI, Weather.SOLEIL): "Saturday in the Park"},
)


def test_covered_weather_uses_the_user_choice():
    assert select_track_query(PROFILE, DayOfWeek.LUNDI, Weather.SOLEIL) == "Here Comes the Sun"


def test_uncovered_weather_uses_the_backup_track():
    assert select_track_query(PROFILE, DayOfWeek.LUNDI, Weather.NEIGE) == "Wake Me Up"


def test_day_and_weather_override_wins_over_the_weather_choice():
    assert select_track_query(PROFILE, DayOfWeek.SAMEDI, Weather.SOLEIL) == "Saturday in the Park"


def test_override_only_applies_to_its_own_weather():
    assert select_track_query(PROFILE, DayOfWeek.SAMEDI, Weather.PLUIE) == "Riders on the Storm"


def test_day_overrides_are_optional():
    profile = UserProfile("u", {}, "Backup", Channel.SMS, {})
    assert select_track_query(profile, DayOfWeek.SAMEDI, Weather.SOLEIL) == "Backup"


@pytest.mark.parametrize("title, artist", [("", "A"), ("T", ""), (None, "A"), ("T", None), ("  ", "A")])
def test_a_track_always_has_a_title_and_an_artist(title, artist):
    with pytest.raises(ValueError):
        Track(title=title, artist=artist, source="x")


def test_message_mentions_day_weather_and_track():
    track = Track(title="Here Comes the Sun", artist="The Beatles", source="itunes")

    message = build_message(track, DayOfWeek.LUNDI, Weather.SOLEIL)

    assert "lundi" in message.subject.lower()
    assert "Here Comes the Sun" in message.body
    assert "The Beatles" in message.body
    assert "soleil" in message.body.lower()
