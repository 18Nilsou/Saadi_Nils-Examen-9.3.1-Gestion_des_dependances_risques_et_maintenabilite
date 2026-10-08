"""Use case testé de bout en bout avec de vrais objets applicatifs et des fakes sur chaque boundary."""
import pytest

from reveil_musical.application.music_chain import MusicFallbackChain
from reveil_musical.application.notifier import NotificationDispatcher
from reveil_musical.application.wake_up import WakeUpUseCase
from reveil_musical.domain.errors import NotificationFailed, ProviderUnavailable, UnknownUser
from reveil_musical.domain.models import Channel, DayOfWeek, Track, UserProfile, WakeUpResult, Weather

PROFILE = UserProfile(
    user_id="u1",
    tracks_by_weather={Weather.SOLEIL: "Here Comes the Sun"},
    backup_track="Wake Me Up",
    preferred_channel=Channel.SMS,
    contacts={Channel.SMS: "+33600000001", Channel.EMAIL: "a@example.com"},
)
LOCAL = Track("Wake Me Up", "Avicii", "local")


class FakeUsers:
    def get(self, user_id):
        if user_id != "u1":
            raise UnknownUser(user_id)
        return PROFILE


class FakeMusic:
    def __init__(self, error=None):
        self.error, self.queries = error, []

    def find_track(self, query):
        self.queries.append(query)
        if self.error:
            raise ProviderUnavailable(self.error)
        return Track(query, "Remote Artist", "remote")


class FakeLocal:
    def find_track(self, query):
        return LOCAL


class FakeSender:
    def __init__(self, fail=False):
        self.fail, self.sent = fail, []

    def send(self, contact, message):
        if self.fail:
            raise NotificationFailed("down")
        self.sent.append((contact, message))


def make(remote=None, sms=None, email=None, log=None):
    remote = remote or FakeMusic()
    senders = {Channel.SMS: sms or FakeSender(), Channel.EMAIL: email or FakeSender()}
    use_case = WakeUpUseCase(
        FakeUsers(),
        MusicFallbackChain([remote, FakeLocal()]),
        NotificationDispatcher(senders, log or FakeSender()),
    )
    return use_case, remote


def test_nominal_wake_up_sends_the_chosen_track_on_the_preferred_channel():
    sms = FakeSender()
    use_case, remote = make(sms=sms)

    result = use_case.execute("u1", DayOfWeek.LUNDI, Weather.SOLEIL)

    assert result == WakeUpResult(Track("Here Comes the Sun", "Remote Artist", "remote"), Channel.SMS, False)
    contact, message = sms.sent[0]
    assert contact == "+33600000001"
    assert "Here Comes the Sun" in message.body and "lundi" in message.subject.lower()


def test_uncovered_weather_searches_the_backup_track():
    use_case, remote = make()

    use_case.execute("u1", DayOfWeek.MARDI, Weather.NEIGE)

    assert remote.queries == ["Wake Me Up"]


def test_music_outage_still_wakes_the_user_with_a_local_track():
    sms = FakeSender()
    use_case, _ = make(remote=FakeMusic(error="HTTP 500"), sms=sms)

    result = use_case.execute("u1", DayOfWeek.LUNDI, Weather.SOLEIL)

    assert result == WakeUpResult(LOCAL, Channel.SMS, True)
    assert len(sms.sent) == 1


def test_channel_outage_switches_to_another_channel():
    email = FakeSender()
    use_case, _ = make(sms=FakeSender(fail=True), email=email)

    result = use_case.execute("u1", DayOfWeek.LUNDI, Weather.SOLEIL)

    assert (result.channel, result.degraded) == (Channel.EMAIL, True)
    assert len(email.sent) == 1


def test_total_outage_is_degraded_but_never_silent():
    log = FakeSender()
    use_case, _ = make(remote=FakeMusic(error="timeout"), sms=FakeSender(True), email=FakeSender(True), log=log)

    result = use_case.execute("u1", DayOfWeek.DIMANCHE, Weather.PLUIE)

    assert result == WakeUpResult(LOCAL, Channel.LOG, True)
    assert log.sent[0][0] == "u1"


def test_unknown_user_is_reported():
    use_case, _ = make()
    with pytest.raises(UnknownUser):
        use_case.execute("ghost", DayOfWeek.LUNDI, Weather.SOLEIL)
