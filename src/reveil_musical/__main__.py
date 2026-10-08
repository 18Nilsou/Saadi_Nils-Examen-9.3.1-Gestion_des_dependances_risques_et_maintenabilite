"""Appel déclenché à l'heure du réveil (l'ordonnancement est hors périmètre).
Usage : python -m reveil_musical <userId> <JOUR> <METEO>"""
import argparse
import logging

from .container import Container, create_container
from .domain.models import DayOfWeek, Weather


def main(argv: list[str] | None = None, container: Container | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reveil_musical")
    parser.add_argument("user_id")
    parser.add_argument("day", type=DayOfWeek, choices=list(DayOfWeek))
    parser.add_argument("weather", type=Weather, choices=list(Weather))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    container = container or create_container()
    result = container.wake_up_use_case().execute(args.user_id, args.day, args.weather)
    print(
        f"Réveil envoyé via {result.channel} : {result.track.title} — {result.track.artist} "
        f"(source={result.track.source}, dégradé={result.degraded})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
