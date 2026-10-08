"""Adapters : ramènent chaque SDK hétérogène au port unique NotificationSender."""
import html
import logging
import unicodedata

from reveil_musical.domain.errors import NotificationFailed
from reveil_musical.domain.models import WakeUpMessage

from .clients import EmailClient, EmailDeliveryError, PushNotifier, PushRejected, SmsGateway, SmsGatewayError

# Alphabet GSM 03.38 de base. Un seul caractère hors de cet alphabet fait passer tout le SMS
# en UCS-2 : 70 caractères par segment au lieu de 160, donc 3 SMS facturés au lieu d'1.
GSM_7 = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
# Typographie courante hors GSM, et extensions GSM (« [ € | »…) qui coûtent 2 caractères chacune.
_TO_GSM = str.maketrans({
    "—": "-", "–": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...",
    "[": "(", "]": ")", "{": "(", "}": ")", "€": "EUR", "|": "/", "~": "-", "\\": "/",
})
SMS_MAX_LENGTH, SMS_MAX_LENGTH_UNICODE = 160, 70


def _gsm_or_unicode(text: str) -> tuple[str, int]:
    """Ramène le texte dans l'alphabet GSM (« Être » -> « Etre ») ; s'il reste un caractère
    intraduisible (titre japonais…), le SMS part en UCS-2 et tient dans un seul segment de 70."""
    text = "".join(
        c if c in GSM_7 else unicodedata.normalize("NFKD", c)[0] for c in text.translate(_TO_GSM)
    )
    return text, SMS_MAX_LENGTH if set(text) <= GSM_7 else SMS_MAX_LENGTH_UNICODE


class EmailNotificationAdapter:
    def __init__(self, client: EmailClient):
        self._client = client

    def send(self, contact: str, message: WakeUpMessage) -> None:
        try:
            # le corps contient un titre venu d'une API tierce : jamais de HTML brut
            self._client.send_mail(contact, message.subject, f"<p>{html.escape(message.body)}</p>")
        except EmailDeliveryError as e:
            raise NotificationFailed(f"email: {e}") from e


class SmsNotificationAdapter:
    def __init__(self, gateway: SmsGateway):
        self._gateway = gateway

    def send(self, contact: str, message: WakeUpMessage) -> None:
        # le corps seul : le sujet, titre de l'email et du push, mangerait la place du morceau
        text, limit = _gsm_or_unicode(message.body)
        try:
            self._gateway.dispatch(contact, text[:limit])
        except SmsGatewayError as e:
            raise NotificationFailed(f"sms: {e}") from e


class PushNotificationAdapter:
    def __init__(self, notifier: PushNotifier):
        self._notifier = notifier

    def send(self, contact: str, message: WakeUpMessage) -> None:
        try:
            self._notifier.notify(contact, message.subject, {"body": message.body})
        except PushRejected as e:
            raise NotificationFailed(f"push: {e}") from e


class LogNotificationSender:
    """Dernier recours : le réveil est au moins tracé, jamais silencieux."""

    _log = logging.getLogger("reveil_musical.fallback")

    def send(self, contact: str, message: WakeUpMessage) -> None:
        self._log.warning("[MODE DEGRADE] réveil de %s : %s - %s", contact, message.subject, message.body)
