"""Karten in die Lerndatenbank übernehmen und im Terminal wiederholen.

Aufruf:
  recall review import data/karten_geprueft.json
  recall review lernen [--limit N]
  recall review stats
Jeder Unterbefehl nimmt --db, falls die Datenbank woanders liegt.
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from recall.console import configure_stdout
from recall.generation.models import Card
from recall.review.db import (
    DEFAULT_DB_PATH,
    connect,
    due_cards,
    import_cards,
    orphaned_cards,
    save_review,
    stats,
)
from recall.review.format import RATING_KEYS, RATINGS
from recall.review.format import lokal as _lokal
from recall.review.scheduling import review

_BEWERTUNGS_HILFE = "  ".join(
    f"{taste} {RATINGS[rating].lower()}" for taste, rating in RATING_KEYS.items()
)


def cmd_import(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    entries = json.loads(Path(args.karten).read_text(encoding="utf-8"))
    if args.auch_verworfene:
        entries = [{**e, "keep": True} for e in entries]
    lernbar = sum(1 for e in entries if e.get("keep", True) is not False)
    print(f"{len(entries)} Karten in der Datei, davon {lernbar} lernbar.")

    neu, aktualisiert = import_cards(conn, entries)
    print(f"{neu} neu übernommen, {aktualisiert} aktualisiert (Lernstand bleibt erhalten).")

    verwaist = orphaned_cards(conn, {Card.model_validate(e).card_id for e in entries})
    if verwaist:
        print(f"\n{len(verwaist)} Karte(n) in der Datenbank kommen in der Datei nicht mehr vor:")
        for row in verwaist:
            print(f"  Seite {row['page_number']}: {row['question'][:70]}")
        print("Sie behalten ihren Lernstand und werden weiter abgefragt.")


def cmd_lernen(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    karten = due_cards(conn, limit=args.limit)
    if not karten:
        print("Nichts fällig.")
        _print_stats(conn)
        return

    print(f"{len(karten)} Karten fällig. Enter zeigt die Antwort, q beendet.\n")
    bewertet = 0
    for card, fsrs_card in karten:
        print(f"--- Seite {card.page_number} ({card.source_file}) ---")
        print(f"F: {card.question}")
        if input().strip().lower() == "q":
            break
        print(f"A: {card.answer}\n")

        eingabe = _frage_bewertung()
        if eingabe is None:
            break

        neuer_stand, log = review(fsrs_card, RATING_KEYS[eingabe])
        # sofort speichern: ein Abbruch mittendrin soll keinen Fortschritt kosten
        save_review(conn, card.card_id, neuer_stand, log)
        bewertet += 1
        print(f"-> wieder fällig: {_lokal(neuer_stand.due)}\n")

    print(f"{bewertet} Karten bewertet.")
    _print_stats(conn)


def _frage_bewertung() -> str | None:
    """Liest eine Bewertung ein. None bedeutet Abbruch."""
    while True:
        eingabe = input(f"{_BEWERTUNGS_HILFE}  (q beendet): ").strip().lower()
        if eingabe == "q":
            return None
        if eingabe in RATING_KEYS:
            return eingabe
        print(f"Bitte {', '.join(RATING_KEYS)} oder q.")


def _print_stats(conn: sqlite3.Connection) -> None:
    s = stats(conn)
    print(
        f"\nKarten: {s['gesamt']} gesamt, {s['lernbar']} lernbar, "
        f"{s['faellig']} fällig, {s['neu']} noch nie gelernt."
    )
    print(f"Bewertungen insgesamt: {s['bewertungen']}")
    if s["naechste"]:
        print(f"Nächste Fälligkeit: {_lokal(datetime.fromisoformat(s['naechste']))}")


def cmd_stats(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    _print_stats(conn)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="befehl", required=True)

    p_import = sub.add_parser("import", help="bewertete Karten in die Datenbank übernehmen")
    p_import.add_argument("karten", help="JSON-Datei aus dem Critic-Lauf")
    p_import.add_argument(
        "--auch-verworfene",
        action="store_true",
        help="vom Critic verworfene Karten trotzdem lernen",
    )
    p_import.set_defaults(handler=cmd_import)

    p_lernen = sub.add_parser("lernen", help="fällige Karten wiederholen")
    p_lernen.add_argument("--limit", type=int, help="höchstens N Karten abfragen")
    p_lernen.set_defaults(handler=cmd_lernen)

    p_stats = sub.add_parser("stats", help="Lernstand anzeigen")
    p_stats.set_defaults(handler=cmd_stats)

    # --db liegt an jedem Unterbefehl statt davor: `recall review stats --db x` ist die
    # Reihenfolge, die man tippt, wenn man es nicht besser weiss.
    for unterbefehl in (p_import, p_lernen, p_stats):
        unterbefehl.add_argument(
            "--db", default=str(DEFAULT_DB_PATH), help="Pfad zur Lerndatenbank"
        )

    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    try:
        args.handler(conn, args)
    finally:
        conn.close()


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(prog="recall review", description=__doc__)
    add_arguments(parser)
    run(parser.parse_args())
