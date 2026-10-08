from reveil_musical.application.notifier import NotificationDispatcher
from reveil_musical.domain.errors import NotificationFailed
from reveil_musical.domain.models import Channel, UserProfile, WakeUpMessage

MESSAGE = WakeUpMessage(subject="s", body="b")


class FakeSender:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent = []

    def send(self, contact, message):
        if self.fail:
            raise NotificationFailed("down")
        self.sent.append((contact, message))


def profile(preferred, contacts):
    return UserProfile("u", {}, "backup", preferred, contacts)


def test_preferred_channel_is_used_when_it_works():
    email, sms, log = FakeSender(), FakeSender(), FakeSender()
    dispatcher = NotificationDispatcher({Channel.EMAIL: email, Channel.SMS: sms}, log)

    channel, degraded = dispatcher.dispatch(
        profile(Channel.SMS, {Channel.EMAIL: "a@x", Channel.SMS: "+33"}), MESSAGE
    )

    assert (channel, degraded) == (Channel.SMS, False)
    assert sms.sent == [("+33", MESSAGE)]
    assert email.sent == []


def test_falls_back_to_another_channel_of_the_user():
    email, sms = FakeSender(), FakeSender(fail=True)
    dispatcher = NotificationDispatcher({Channel.EMAIL: email, Channel.SMS: sms}, FakeSender())

    channel, degraded = dispatcher.dispatch(
        profile(Channel.SMS, {Channel.SMS: "+33", Channel.EMAIL: "a@x"}), MESSAGE
    )

    assert (channel, degraded) == (Channel.EMAIL, True)
    assert email.sent == [("a@x", MESSAGE)]


def test_channel_without_registered_sender_is_skipped():
    log = FakeSender()
    dispatcher = NotificationDispatcher({}, log)

    channel, degraded = dispatcher.dispatch(profile(Channel.PUSH, {Channel.PUSH: "tok"}), MESSAGE)

    assert (channel, degraded) == (Channel.LOG, True)


def test_last_resort_when_every_channel_fails_so_never_silent():
    log = FakeSender()
    dispatcher = NotificationDispatcher({Channel.EMAIL: FakeSender(fail=True)}, log)

    channel, degraded = dispatcher.dispatch(profile(Channel.EMAIL, {Channel.EMAIL: "a@x"}), MESSAGE)

    assert (channel, degraded) == (Channel.LOG, True)
    assert log.sent == [("u", MESSAGE)]
