"""Faux SDK de notification (aucun envoi réel) aux interfaces volontairement hétérogènes,
comme le seraient trois fournisseurs différents. Chacun a son propre type d'erreur.
Les contacts sont masqués dans les logs (données personnelles, RGPD)."""
import logging


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"


def _mask_phone(phone: str) -> str:
    return phone[:4] + "*" * max(len(phone) - 6, 0) + phone[-2:]


class EmailDeliveryError(Exception):
    pass


class SmsGatewayError(Exception):
    pass


class PushRejected(Exception):
    pass


class EmailClient:
    _log = logging.getLogger("reveil_musical.mock.email")

    def send_mail(self, to: str, subject: str, html_body: str) -> None:
        self._log.info("To: %s | Subject: %s | %s", _mask_email(to), subject, html_body)


class SmsGateway:
    _log = logging.getLogger("reveil_musical.mock.sms")

    def dispatch(self, phone: str, text: str) -> None:
        self._log.info("SMS -> %s : %s", _mask_phone(phone), text)


class PushNotifier:
    _log = logging.getLogger("reveil_musical.mock.push")

    def notify(self, device_token: str, title: str, payload: dict) -> None:
        self._log.info("PUSH [%s***] %s %s", device_token[:4], title, payload)
