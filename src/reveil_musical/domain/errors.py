class ProviderUnavailable(Exception):
    """Un fournisseur musical est en panne, limité ou a répondu un format invalide."""


class NotificationFailed(Exception):
    """Un canal de notification n'a pas pu délivrer le message."""


class UnknownUser(Exception):
    pass
