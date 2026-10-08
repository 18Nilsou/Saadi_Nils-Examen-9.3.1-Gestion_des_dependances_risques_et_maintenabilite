"""Appel déclenché à l'heure du réveil (l'ordonnancement est hors périmètre).
Usage : python -m reveil_musical <userId> <JOUR> <METEO>"""
import argparse
import logging

from .container import Container, create_container
from .domain.errors import UnknownUser
from .domain.models import DayOfWeek, Weather

_log = logging.getLogger("reveil_musical")


def _wake(container: Container, user_id: str, day: DayOfWeek, weather: Weather) -> int:
    """Un réveil. Codes de sortie : 0 envoyé, 2 utilisateur inconnu, 1 panne non rattrapable
    (ex. service utilisateurs injoignable) : tracée en CRITICAL pour que l'ordonnanceur alerte."""
    try:
        result = container.wake_up_use_case().execute(user_id, day, weather)
    except UnknownUser:
        _log.error("utilisateur inconnu : %s", user_id)
        return 2
    except Exception:
        _log.critical("RÉVEIL NON LIVRÉ pour %s (%s, %s)", user_id, day, weather, exc_info=True)
        return 1
    print(
        f"Réveil envoyé via {result.channel} : {result.track.title} — {result.track.artist} "
        f"(source={result.track.source}, dégradé={result.degraded})"
    )
    return 0


def main(argv: list[str] | None = None, container: Container | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reveil_musical")
    parser.add_argument("user_id")
    parser.add_argument("day", type=DayOfWeek, choices=list(DayOfWeek))
    parser.add_argument("weather", type=Weather, choices=list(Weather))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return _wake(container or create_container(), args.user_id, args.day, args.weather)


if __name__ == "__main__":
    raise SystemExit(main())
