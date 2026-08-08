"""Ein Befehl für die ganze Pipeline.

  recall ingest   data/folien.pdf                 PDF in Chunks zerlegen und ansehen
  recall generate data/folien.pdf --out k.json    Karten daraus generieren
  recall critic   k.json --out k_geprueft.json    Karten bewerten und entdoppeln
  recall review   import|lernen|stats             Lerndatenbank füllen und abfragen
  recall ui                                       dasselbe im Browser

Jede Stufe schreibt JSON und liest JSON: die Zwischenstände lassen sich ansehen und
von Hand korrigieren, bevor die nächste Stufe darauf losgeht.
"""

import argparse

from recall.console import configure_stdout
from recall.critic import cli as critic_cli
from recall.generation import cli as generation_cli
from recall.ingestion import cli as ingestion_cli
from recall.review import cli as review_cli
from recall.ui import cli as ui_cli

BEFEHLE = [
    ("ingest", "PDF in gesäuberte Chunks zerlegen", ingestion_cli),
    ("generate", "Lernkarten aus einem PDF generieren", generation_cli),
    ("critic", "generierte Karten bewerten und entdoppeln", critic_cli),
    ("review", "Lerndatenbank füllen und im Terminal wiederholen", review_cli),
    ("ui", "Weboberfläche starten", ui_cli),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recall",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="stufe", required=True)
    for name, hilfe, modul in BEFEHLE:
        unterbefehl = sub.add_parser(
            name,
            help=hilfe,
            description=modul.__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        modul.add_arguments(unterbefehl)
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdout()
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
