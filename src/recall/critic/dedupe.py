"""Doppelte Karten finden - zweistufig.

Derselbe Begriff wird über mehrere Folien hinweg wiederholt, der Generator sieht aber
immer nur eine Folie und kann das nicht wissen.

Stufe 1 sucht rein textuell Kandidaten, Stufe 2 lässt das Modell entscheiden. Die
Trennung ist notwendig, nicht vorsichtshalber: im echten Foliensatz ist das ähnlichste
Fragenpaar überhaupt ("Wie beginnt der agglomerative..." / "...divisive Prozess beim
hierarchischen Clustering?") gerade kein Duplikat.
"""

import difflib
import re

from recall.critic.models import Verdict
from recall.generation.models import Card
from recall.llm_client import complete
from recall.parsing import parse_json_list

DEFAULT_THRESHOLD = 0.75

_PROMPT_TEMPLATE = """\
Du prüfst Paare von Lernkarten-Fragen auf inhaltliche Dopplung.

Ein Paar ist nur dann doppelt, wenn beide Fragen dasselbe Wissen abfragen und man mit
einer Antwort beide beantworten könnte. Ähnlicher Wortlaut allein genügt nicht:
gegensätzliche oder komplementäre Begriffe (etwa agglomerativ und divisiv) oder
verschiedene Aspekte desselben Themas sind keine Dopplung.

Antworte ausschließlich mit JSON in genau diesem Format, ein Eintrag pro Paar, ohne
weiteren Text:
[{{"paar": 0, "gleich": true}}]

Paare:
{pairs}
"""

_PAIR_TEMPLATE = """\
[{index}] A: {a}
     B: {b}"""

_NON_WORD_RE = re.compile(r"\W+", re.UNICODE)


def _normalize(question: str) -> str:
    return _NON_WORD_RE.sub(" ", question.lower()).strip()


def find_duplicate_candidates(
    cards: list[Card], threshold: float = DEFAULT_THRESHOLD
) -> list[tuple[int, int]]:
    """Indexpaare (i, j) mit i < j, deren Fragen sich stark ähneln."""
    normalized = [_normalize(c.question) for c in cards]
    pairs = []
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            if difflib.SequenceMatcher(None, normalized[i], normalized[j]).ratio() > threshold:
                pairs.append((i, j))
    return pairs


def build_dedupe_prompt(cards: list[Card], pairs: list[tuple[int, int]]) -> str:
    rendered = "\n".join(
        _PAIR_TEMPLATE.format(index=n, a=cards[i].question, b=cards[j].question)
        for n, (i, j) in enumerate(pairs)
    )
    return _PROMPT_TEMPLATE.format(pairs=rendered)


def parse_dedupe_response(response: str, pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Filtert die Kandidaten auf die vom Modell bestätigten Paare.

    Fehlt ein Urteil, gilt das Paar als nicht doppelt - im Zweifel bleibt die Karte.
    """
    raw = parse_json_list(response)
    confirmed = []
    for item in raw:
        if not isinstance(item, dict) or "paar" not in item or "gleich" not in item:
            raise ValueError(f"Eintrag ohne paar/gleich: {item!r}")
        try:
            index = int(item["paar"])
        except (TypeError, ValueError) as e:
            raise ValueError(f"Paar-Index ist keine Zahl: {item!r}") from e
        if not 0 <= index < len(pairs):
            raise ValueError(f"Paar-Index {index} liegt außerhalb der Kandidaten ({len(pairs)})")
        if item["gleich"]:
            confirmed.append(pairs[index])
    return confirmed


def find_duplicates(cards: list[Card], threshold: float = DEFAULT_THRESHOLD) -> list[Verdict]:
    """Urteile für die als doppelt bestätigten Karten. Die frühere Karte bleibt."""
    candidates = find_duplicate_candidates(cards, threshold)
    if not candidates:
        return []
    confirmed = parse_dedupe_response(complete(build_dedupe_prompt(cards, candidates)), candidates)
    verdicts: dict[str, Verdict] = {}
    for i, j in confirmed:
        card = cards[j]
        verdicts[card.card_id] = Verdict(
            card_id=card.card_id,
            keep=False,
            issue="duplikat",
            reason=f"Fragt dasselbe ab wie die Karte auf Seite {cards[i].page_number}.",
        )
    return list(verdicts.values())
