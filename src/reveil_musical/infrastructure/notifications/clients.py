"""Faux SDK de notification (aucun envoi réel) aux interfaces volontairement hétérogènes,
comme le seraient trois fournisseurs différents. Chacun a son propre type d'erreur."""
import logging


class EmailDeliveryError(Exception):
    pass


class SmsGatewayError(Exception):
    pass


class PushRejected(Exception):
    pass


class EmailClient:
    _log = logging.getLogger("reveil_musical.mock.email")

    def send_mail(self, to: str, subject: str, html_body: str) -> None:
        self._log.info("To: %s | Subject: %s | %s", to, subject, html_body)


class SmsGateway:
    _log = logging.getLogger("reveil_musical.mock.sms")

    def dispatch(self, phone: str, text: str) -> None:
        self._log.info("SMS -> %s : %s", phone, text)


class PushNotifier:
    _log = logging.getLogger("reveil_musical.mock.push")

    def notify(self, device_token: str, title: str, payload: dict) -> None:
        self._log.info("PUSH [%s] %s %s", device_token, title, payload)
