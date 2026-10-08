import pytest
from reveil_musical.infrastructure.users.last_known import (
    LastKnownUserPreferencesRepository,
    open_profile_store,
)

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


# --- Dernier profil connu (service utilisateurs en panne) ---

class FlakyUsers:
    def __init__(self):
        self.down = False

    def get(self, user_id):
        if self.down:
            raise ConnectionError("service utilisateurs injoignable")
        return InMemoryUserPreferencesRepository(DEMO_PROFILES).get(user_id)


def test_outage_falls_back_on_the_last_known_profile():
    inner = FlakyUsers()
    repo = LastKnownUserPreferencesRepository(inner, {})
    profile = repo.get("u1")
    inner.down = True

    assert repo.get("u1") == profile


def test_outage_without_a_known_profile_still_raises():
    inner = FlakyUsers()
    inner.down = True
    with pytest.raises(ConnectionError):
        LastKnownUserPreferencesRepository(inner, {}).get("u1")


def test_a_deleted_user_is_forgotten_and_never_woken_up_again():
    store = {}
    repo = LastKnownUserPreferencesRepository(InMemoryUserPreferencesRepository(DEMO_PROFILES), store)
    store["nobody"] = DEMO_PROFILES[0]
    with pytest.raises(UnknownUser):
        repo.get("nobody")
    assert "nobody" not in store


def test_a_store_that_cannot_write_never_blocks_the_wake_up():
    class ReadOnly(dict):
        def __setitem__(self, key, value):
            raise OSError("disque plein")

    repo = LastKnownUserPreferencesRepository(InMemoryUserPreferencesRepository(DEMO_PROFILES), ReadOnly())
    assert repo.get("u1").user_id == "u1"


def test_the_file_store_survives_from_one_round_to_the_next(tmp_path):
    path = str(tmp_path / "profils.db")
    LastKnownUserPreferencesRepository(InMemoryUserPreferencesRepository(DEMO_PROFILES), open_profile_store(path)).get("u1")
    inner = FlakyUsers()
    inner.down = True  # tournée suivante, nouveau processus, service en panne

    assert LastKnownUserPreferencesRepository(inner, open_profile_store(path)).get("u1").user_id == "u1"
