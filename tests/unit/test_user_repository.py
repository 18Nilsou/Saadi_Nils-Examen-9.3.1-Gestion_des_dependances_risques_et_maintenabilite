import pytest

from reveil_musical.domain.errors import UnknownUser
from reveil_musical.domain.models import Channel, Weather
from reveil_musical.infrastructure.users.in_memory import DEMO_PROFILES, InMemoryUserPreferencesRepository


def test_returns_the_seeded_profile():
    repo = InMemoryUserPreferencesRepository(DEMO_PROFILES)

    assert repo.get("u1").user_id == "u1"


def test_unknown_user_raises_a_domain_error():
    with pytest.raises(UnknownUser):
        InMemoryUserPreferencesRepository(DEMO_PROFILES).get("nobody")


def test_demo_data_covers_each_channel_and_an_uncovered_weather():
    channels = {p.preferred_channel for p in DEMO_PROFILES}
    assert channels == {Channel.EMAIL, Channel.SMS, Channel.PUSH}
    assert any(len(p.tracks_by_weather) < len(Weather) for p in DEMO_PROFILES)
    assert any(p.tracks_by_day for p in DEMO_PROFILES)
