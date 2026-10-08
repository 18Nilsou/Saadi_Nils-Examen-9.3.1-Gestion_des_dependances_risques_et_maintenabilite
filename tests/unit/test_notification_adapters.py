import logging

from fakes import SdkSpy as Spy

from reveil_musical.domain.models import WakeUpMessage
from reveil_musical.infrastructure.notifications.adapters import (
    EmailNotificationAdapter,
    LogNotificationSender,
    PushNotificationAdapter,
    SmsNotificationAdapter,
)
from reveil_musical.infrastructure.notifications.clients import (
    EmailClient,
    PushNotifier,
    SmsGateway,
)

MESSAGE = WakeUpMessage(subject="Bon lundi !", body="Votre morceau : Clouds — Zara Larsson.")


def test_email_adapter_maps_to_send_mail_with_html_body():
    spy = Spy()
    EmailNotificationAdapter(spy).send("a@example.com", MESSAGE)
    assert spy.calls == [("a@example.com", "Bon lundi !", f"<p>{MESSAGE.body}</p>")]


def test_sms_adapter_flattens_and_truncates_to_160_chars():
    spy = Spy()
    long_message = WakeUpMessage(subject="S", body="x" * 300)
    SmsNotificationAdapter(spy).send("+33600000000", long_message)
    phone, text = spy.calls[0]
    assert phone == "+33600000000"
    assert len(text) == 160
    assert text.startswith("S - x")


def test_push_adapter_maps_to_title_and_payload():
    spy = Spy()
    PushNotificationAdapter(spy).send("token", MESSAGE)
    assert spy.calls == [("token", "Bon lundi !", {"body": MESSAGE.body})]


def test_fake_sdks_write_to_the_log(caplog):
    caplog.set_level(logging.INFO)
    EmailNotificationAdapter(EmailClient()).send("a@example.com", MESSAGE)
    SmsNotificationAdapter(SmsGateway()).send("+336", MESSAGE)
    PushNotificationAdapter(PushNotifier()).send("tok", MESSAGE)
    LogNotificationSender().send("u1", MESSAGE)
    assert [r.name.split(".")[-1] for r in caplog.records] == ["email", "sms", "push", "fallback"]
    assert all("Bon lundi" in r.getMessage() for r in caplog.records)


def test_fake_sdks_never_log_contacts_in_clear(caplog):
    caplog.set_level(logging.INFO)
    EmailClient().send_mail("alice@example.com", "s", "b")
    SmsGateway().dispatch("+33600000001", "t")
    PushNotifier().notify("device-token-u3", "t", {})

    assert "alice@" not in caplog.text and "al***@example.com" in caplog.text
    assert "+33600000001" not in caplog.text and "+336******01" in caplog.text
    assert "device-token-u3" not in caplog.text and "devi***" in caplog.text
