"""PDF einlesen, Lernkarten generieren und als JSON speichern.

Aufruf: recall generate data/<foliensatz>.pdf [--limit N] [--out data/karten.json]
"""

import argparse
import json
from pathlib import Path

from google.genai import errors

from recall.console import configure_stdout
from recall.generation.generate import generate_cards
from recall.ingestion.cleaning import clean_chunks
from recall.ingestion.pdf import extract_chunks


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pdf", help="Pfad zum PDF")
    parser.add_argument("--limit", type=int, help="nur die ersten N Chunks verarbeiten")
    parser.add_argument("--out", help="Karten als JSON in diese Datei schreiben")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    chunks = clean_chunks(extract_chunks(args.pdf))
    if args.limit:
        chunks = chunks[: args.limit]

    cards = []
    failures = 0
    for chunk in chunks:
        try:
            new_cards = generate_cards(chunk)
        except ValueError as e:
            failures += 1
            print(f"!! Seite {chunk.page_number}: {e}")
            continue
        except errors.APIError as e:
            # z. B. Tageskontingent erschöpft: abbrechen, aber Teilergebnis behalten
            print(f"!! Abbruch bei Seite {chunk.page_number}: API-Fehler {e.code} ({e.status})")
            break
        cards.extend(new_cards)
        for card in new_cards:
            print(f"--- Seite {card.page_number} ---")
            print(f"F: {card.question}")
            print(f"A: {card.answer}")
            print()

    print(f"{len(cards)} Karten aus {len(chunks)} Chunks ({failures} Fehler).")

    if args.out:
        Path(args.out).write_text(
            json.dumps([c.model_dump() for c in cards], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Gespeichert: {args.out}")


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    run(parser.parse_args())
