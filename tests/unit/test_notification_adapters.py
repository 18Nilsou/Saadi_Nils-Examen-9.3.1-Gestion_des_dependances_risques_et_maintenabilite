import logging

import pytest

from reveil_musical.domain.errors import NotificationFailed
from reveil_musical.domain.models import WakeUpMessage
from reveil_musical.infrastructure.notifications.adapters import (
    EmailNotificationAdapter,
    LogNotificationSender,
    PushNotificationAdapter,
    SmsNotificationAdapter,
)
from reveil_musical.infrastructure.notifications.clients import (
    EmailClient,
    EmailDeliveryError,
    PushNotifier,
    PushRejected,
    SmsGateway,
    SmsGatewayError,
)

MESSAGE = WakeUpMessage(subject="Bon lundi !", body="Votre morceau : Clouds — Zara Larsson.")


class Spy:
    """Enregistre l'appel reçu, quelle que soit la signature du faux SDK."""

    def __init__(self, error: Exception | None = None):
        self.calls = []
        self.error = error

    def _record(self, *args):
        self.calls.append(args)
        if self.error:
            raise self.error

    send_mail = dispatch = notify = _record


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


@pytest.mark.parametrize(
    "adapter_cls, error",
    [
        (EmailNotificationAdapter, EmailDeliveryError("smtp down")),
        (SmsNotificationAdapter, SmsGatewayError("quota")),
        (PushNotificationAdapter, PushRejected("bad token")),
    ],
)
def test_adapters_translate_sdk_errors_into_domain_error(adapter_cls, error):
    with pytest.raises(NotificationFailed):
        adapter_cls(Spy(error)).send("contact", MESSAGE)


def test_fake_sdks_write_to_the_log(caplog):
    caplog.set_level(logging.INFO)
    EmailNotificationAdapter(EmailClient()).send("a@example.com", MESSAGE)
    SmsNotificationAdapter(SmsGateway()).send("+336", MESSAGE)
    PushNotificationAdapter(PushNotifier()).send("tok", MESSAGE)
    LogNotificationSender().send("u1", MESSAGE)
    assert [r.name.split(".")[-1] for r in caplog.records] == ["email", "sms", "push", "fallback"]
    assert all("Bon lundi" in r.getMessage() for r in caplog.records)
