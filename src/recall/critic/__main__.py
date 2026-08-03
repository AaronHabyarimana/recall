"""CLI: generierte Karten bewerten und mit Urteil wieder als JSON speichern.

Aufruf: uv run python -m recall.critic data/karten.json [--limit N] [--out karten_geprueft.json]

Es wird nichts gelöscht: jede Karte bleibt erhalten und bekommt keep/issue/reason dazu.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from google.genai import errors

from recall.critic.dedupe import find_duplicates
from recall.critic.judge import BATCH_SIZE, judge_cards
from recall.critic.models import Verdict
from recall.generation.models import Card


def load_cards(path: str) -> list[Card]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Card.model_validate(item) for item in raw]


def merge_verdicts(judgements: list[Verdict], duplicates: list[Verdict]) -> dict[str, Verdict]:
    """Duplikat-Urteile haben Vorrang: die Einzelprüfung sieht die andere Karte nicht."""
    merged = {v.card_id: v for v in judgements}
    merged.update({v.card_id: v for v in duplicates})
    return merged


def _report(cards: list[Card], verdicts: dict[str, Verdict]) -> None:
    judged = [c for c in cards if c.card_id in verdicts]
    dropped = [c for c in judged if not verdicts[c.card_id].keep]
    print(f"\n{len(judged) - len(dropped)} von {len(judged)} bewerteten Karten behalten.")
    if len(judged) < len(cards):
        print(f"{len(cards) - len(judged)} Karten wurden nicht bewertet.")
    if not dropped:
        return
    issues = Counter(verdicts[c.card_id].issue for c in dropped)
    print("Verworfen: " + ", ".join(f"{issue} {n}" for issue, n in issues.most_common()))
    print()
    for card in dropped:
        verdict = verdicts[card.card_id]
        print(f"--- Seite {card.page_number} [{verdict.issue}] ---")
        print(f"F: {card.question}")
        print(f"   {verdict.reason}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("karten", help="Pfad zur JSON-Datei mit generierten Karten")
    parser.add_argument("--limit", type=int, help="nur die ersten N Karten prüfen")
    parser.add_argument("--out", help="bewertete Karten in diese Datei schreiben")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Karten pro Anfrage (Standard {BATCH_SIZE})",
    )
    args = parser.parse_args()

    cards = load_cards(args.karten)
    if args.limit:
        cards = cards[: args.limit]
    print(f"{len(cards)} Karten geladen.")

    judgements: list[Verdict] = []
    duplicates: list[Verdict] = []
    try:
        judgements = judge_cards(cards, batch_size=args.batch_size)
        duplicates = find_duplicates(cards)
    except errors.APIError as e:
        # z. B. Tageskontingent erschöpft: abbrechen, aber Teilergebnis behalten
        print(f"!! Abbruch: API-Fehler {e.code} ({e.status})")

    verdicts = merge_verdicts(judgements, duplicates)
    _report(cards, verdicts)

    if args.out:
        payload = []
        for card in cards:
            verdict = verdicts.get(card.card_id)
            entry = card.model_dump()
            entry["keep"] = verdict.keep if verdict else None
            entry["issue"] = verdict.issue if verdict else None
            entry["reason"] = verdict.reason if verdict else "nicht bewertet"
            payload.append(entry)
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nGespeichert: {args.out}")


if __name__ == "__main__":
    main()
