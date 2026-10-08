import logging

from fakes import SdkSpy as Spy

from reveil_musical.domain.models import WakeUpMessage
from reveil_musical.infrastructure.notifications.adapters import (
    GSM_7,
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



def test_email_adapter_escapes_html_coming_from_a_music_provider():
    spy = Spy()
    EmailNotificationAdapter(spy).send("a@example.com", WakeUpMessage("S", "<img src=x onerror=alert(1)> & co"))
    assert spy.calls[0][2] == "<p>&lt;img src=x onerror=alert(1)&gt; &amp; co</p>"

def sms_text(body: str) -> str:
    spy = Spy()
    SmsNotificationAdapter(spy).send("+33600000000", WakeUpMessage(subject="Bon lundi !", body=body))
    return spy.calls[0][1]


def test_sms_adapter_sends_the_body_truncated_to_160_chars():
    # le sujet sert de titre à l'email et au push ; en SMS il mangerait la place du morceau
    assert sms_text("x" * 300) == "x" * 160


def test_sms_stays_in_the_gsm_alphabet_so_one_message_is_billed():
    """Régression : « — » (hors GSM-7) passait tout le SMS en UCS-2, 70 car./segment : 3 SMS facturés."""
    text = sms_text("Votre morceau : Être là — L’été [Remastered] … ç € | ~ {x} \\")

    assert text == "Votre morceau : Etre là - L'été (Remastered) ... c EUR / - (x) /"
    assert set(text) <= GSM_7


def test_an_sms_that_cannot_stay_in_gsm_fits_in_one_unicode_segment():
    text = sms_text("Votre morceau : 夜に駆ける — YOASOBI." + "x" * 100)

    assert text.startswith("Votre morceau : 夜に駆ける - YOASOBI.") and len(text) == 70


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
    assert all("Clouds" in r.getMessage() for r in caplog.records)


def test_fake_sdks_never_log_contacts_in_clear(caplog):
    caplog.set_level(logging.INFO)
    EmailClient().send_mail("alice@example.com", "s", "b")
    SmsGateway().dispatch("+33600000001", "t")
    PushNotifier().notify("device-token-u3", "t", {})

    assert "alice@" not in caplog.text and "al***@example.com" in caplog.text
    assert "+33600000001" not in caplog.text and "+336******01" in caplog.text
    assert "device-token-u3" not in caplog.text and "devi***" in caplog.text
