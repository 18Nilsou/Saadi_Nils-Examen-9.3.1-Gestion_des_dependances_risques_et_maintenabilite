"""Appel déclenché à l'heure du réveil (l'ordonnancement est hors périmètre).

Usage :
  python -m reveil_musical <userId> <JOUR> <METEO>
  python -m reveil_musical --batch reveils.csv     # une ligne « user,jour,meteo » par réveil

Le mode lot est le mode de production : l'ordonnanceur lance la tournée dans UN processus,
le conteneur est construit une fois, donc cache, quota et coupe-circuit sont partagés
entre tous les réveils (un processus par réveil les remettrait à zéro à chaque fois)."""
import argparse
import csv
import logging

from .container import Container, create_container
from .domain.errors import UnknownUser
from .domain.models import DayOfWeek, Weather

_log = logging.getLogger("reveil_musical")


def jour(text: str) -> DayOfWeek:
    return DayOfWeek(text.strip().upper())


def meteo(text: str) -> Weather:
    return Weather(text.strip().upper())


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


def _wake_batch(container: Container, path: str) -> int:
    """Une ligne en erreur est tracée et n'empêche jamais les réveils suivants."""
    status = 0
    with open(path, newline="", encoding="utf-8") as f:
        for number, row in enumerate(csv.reader(f), start=1):
            if not row or row[0].lstrip().startswith("#"):
                continue
            try:
                user_id, day, weather = row
                status = max(status, _wake(container, user_id.strip(), jour(day), meteo(weather)))
            except ValueError as e:
                _log.error("ligne %d ignorée (%s) : %s", number, ",".join(row), e)
                status = max(status, 1)
    return status


def main(argv: list[str] | None = None, container: Container | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reveil_musical")
    parser.add_argument("user_id", nargs="?")
    parser.add_argument("day", nargs="?", type=jour, choices=list(DayOfWeek))
    parser.add_argument("weather", nargs="?", type=meteo, choices=list(Weather))
    parser.add_argument("--batch", metavar="FICHIER.csv", help="tournée de réveils : user,jour,meteo par ligne")
    args = parser.parse_args(argv)
    if not args.batch and None in (args.user_id, args.day, args.weather):
        parser.error("donnez <userId> <JOUR> <METEO>, ou --batch FICHIER.csv")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    container = container or create_container()
    if args.batch:
        return _wake_batch(container, args.batch)
    return _wake(container, args.user_id, args.day, args.weather)


if __name__ == "__main__":
    raise SystemExit(main())
