"""CLI: Karten in die Lerndatenbank übernehmen und wiederholen.

Aufruf:
  uv run python -m recall.review import data/karten_geprueft.json
  uv run python -m recall.review lernen [--limit N]
  uv run python -m recall.review stats
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from fsrs import Rating

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
from recall.review.scheduling import review

_RATING_KEYS = {
    "1": Rating.Again,
    "2": Rating.Hard,
    "3": Rating.Good,
    "4": Rating.Easy,
}


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

        neuer_stand, log = review(fsrs_card, _RATING_KEYS[eingabe])
        # sofort speichern: ein Abbruch mittendrin soll keinen Fortschritt kosten
        save_review(conn, card.card_id, neuer_stand, log)
        bewertet += 1
        print(f"-> wieder fällig: {_lokal(neuer_stand.due)}\n")

    print(f"{bewertet} Karten bewertet.")
    _print_stats(conn)


def _frage_bewertung() -> str | None:
    """Liest eine Bewertung ein. None bedeutet Abbruch."""
    while True:
        eingabe = input("1 nochmal  2 schwer  3 gut  4 leicht  (q beendet): ").strip().lower()
        if eingabe == "q":
            return None
        if eingabe in _RATING_KEYS:
            return eingabe
        print("Bitte 1, 2, 3, 4 oder q.")


def _lokal(zeitpunkt: datetime) -> str:
    return f"{zeitpunkt.astimezone():%d.%m.%Y %H:%M}"


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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Pfad zur Lerndatenbank")
    sub = parser.add_subparsers(dest="befehl", required=True)

    p_import = sub.add_parser("import", help="bewertete Karten in die Datenbank übernehmen")
    p_import.add_argument("karten", help="JSON-Datei aus dem Critic-Lauf")
    p_import.add_argument(
        "--auch-verworfene",
        action="store_true",
        help="vom Critic verworfene Karten trotzdem lernen",
    )
    p_import.set_defaults(func=cmd_import)

    p_lernen = sub.add_parser("lernen", help="fällige Karten wiederholen")
    p_lernen.add_argument("--limit", type=int, help="höchstens N Karten abfragen")
    p_lernen.set_defaults(func=cmd_lernen)

    p_stats = sub.add_parser("stats", help="Lernstand anzeigen")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    conn = connect(args.db)
    try:
        args.func(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
