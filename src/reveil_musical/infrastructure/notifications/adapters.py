"""Adapters : ramènent chaque SDK hétérogène au port unique NotificationSender."""
import logging

from reveil_musical.domain.errors import NotificationFailed
from reveil_musical.domain.models import WakeUpMessage

from .clients import EmailClient, EmailDeliveryError, PushNotifier, PushRejected, SmsGateway, SmsGatewayError

SMS_MAX_LENGTH = 160


class EmailNotificationAdapter:
    def __init__(self, client: EmailClient):
        self._client = client

    def send(self, contact: str, message: WakeUpMessage) -> None:
        try:
            self._client.send_mail(contact, message.subject, f"<p>{message.body}</p>")
        except EmailDeliveryError as e:
            raise NotificationFailed(f"email: {e}") from e


class SmsNotificationAdapter:
    def __init__(self, gateway: SmsGateway):
        self._gateway = gateway

    def send(self, contact: str, message: WakeUpMessage) -> None:
        text = f"{message.subject} - {message.body}"[:SMS_MAX_LENGTH]
        try:
            self._gateway.dispatch(contact, text)
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
