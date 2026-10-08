import logging
from collections.abc import Mapping

from reveil_musical.domain.errors import NotificationFailed
from reveil_musical.domain.models import Channel, UserProfile, WakeUpMessage
from reveil_musical.domain.ports import NotificationSender

_log = logging.getLogger(__name__)


class NotificationDispatcher:
    """Strategy : choisit le sender selon le canal préféré, puis se replie sur les autres
    canaux connus de l'utilisateur, puis sur le dernier recours."""

    def __init__(self, senders: Mapping[Channel, NotificationSender], last_resort: NotificationSender):
        self._senders = senders
        self._last_resort = last_resort

    def dispatch(self, profile: UserProfile, message: WakeUpMessage) -> tuple[Channel, bool]:
        ordered = [profile.preferred_channel] + [c for c in profile.contacts if c != profile.preferred_channel]
        for channel in ordered:
            sender = self._senders.get(channel)
            if sender is None or channel not in profile.contacts:
                continue
            try:
                sender.send(profile.contacts[channel], message)
                return channel, channel != profile.preferred_channel
            except NotificationFailed as e:
                _log.warning("canal %s en échec : %s", channel, e)
        self._last_resort.send(profile.user_id, message)
        return Channel.LOG, True
