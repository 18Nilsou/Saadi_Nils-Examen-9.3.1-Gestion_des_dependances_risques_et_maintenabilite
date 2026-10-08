from reveil_musical.domain.models import Channel, DayOfWeek, Track, UserProfile, Weather
from reveil_musical.domain.rules import build_message, select_track_query

PROFILE = UserProfile(
    user_id="u1",
    tracks_by_weather={Weather.SOLEIL: "Here Comes the Sun", Weather.PLUIE: "Riders on the Storm"},
    backup_track="Wake Me Up",
    preferred_channel=Channel.EMAIL,
    contacts={Channel.EMAIL: "u1@example.com"},
)


def test_covered_weather_uses_the_user_choice():
    assert select_track_query(PROFILE, Weather.SOLEIL) == "Here Comes the Sun"


def test_uncovered_weather_uses_the_backup_track():
    assert select_track_query(PROFILE, Weather.NEIGE) == "Wake Me Up"


def test_message_mentions_day_weather_and_track():
    track = Track(title="Here Comes the Sun", artist="The Beatles", source="itunes")

    message = build_message(track, DayOfWeek.LUNDI, Weather.SOLEIL)

    assert "lundi" in message.subject.lower()
    assert "Here Comes the Sun" in message.body
    assert "The Beatles" in message.body
    assert "soleil" in message.body.lower()
