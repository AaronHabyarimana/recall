"""Einzelbewertung von Karten: taugt die Karte zum Lernen?

Bewertet wird gebatcht (mehrere Karten pro Anfrage), weil das Free-Tier ein
Tageskontingent an Anfragen hat und nicht an Token.
"""

from recall.critic.models import Verdict
from recall.generation.models import Card
from recall.llm_client import complete
from recall.parsing import parse_json_list

BATCH_SIZE = 10

_PROMPT_TEMPLATE = """\
Du prüfst Lernkarten, die aus Vorlesungsfolien erzeugt wurden, auf Tauglichkeit für die \
Prüfungsvorbereitung.

Verwirf eine Karte, wenn einer dieser Punkte zutrifft:
- "kontextabhaengig": Die Frage ist ohne die Folie nicht beantwortbar (verweist auf "hier", \
eine Abbildung, ein Beispiel oder darauf, was "genannt" oder "gezeigt" wird).
- "trivia": Es geht nicht um ein prüfungsrelevantes Konzept, sondern um eine Illustration, \
eine Literatur- oder Quellenangabe, ein Werkzeug oder eine Organisationsinfo zur Vorlesung.
- "unklar": Die Antwort beantwortet die Frage nicht, ist inhaltsleer oder widersprüchlich.

Behalte im Zweifel. Eine fachlich korrekte, eigenständig verständliche Frage zu einem \
Konzept ist eine gute Karte, auch wenn sie einfach ist.

Antworte ausschließlich mit JSON in genau diesem Format, ein Eintrag pro Karte, ohne \
weiteren Text:
[{{"index": 0, "keep": true, "issue": null, "reason": "..."}}]

"issue" ist einer der Werte oben oder null, wenn keep true ist. "reason" ist ein kurzer \
deutscher Satz.

Karten:
{cards}
"""

_CARD_TEMPLATE = """\
[{index}] Frage: {question}
     Antwort: {answer}"""

_VALID_ISSUES = {"kontextabhaengig", "trivia", "unklar"}


def build_judge_prompt(cards: list[Card]) -> str:
    rendered = "\n".join(
        _CARD_TEMPLATE.format(index=i, question=c.question, answer=c.answer)
        for i, c in enumerate(cards)
    )
    return _PROMPT_TEMPLATE.format(cards=rendered)


def parse_verdicts(response: str, cards: list[Card]) -> list[Verdict]:
    """Parst die Modellantwort zu Urteilen.

    Referenziert wird über den Index im Batch, nicht über die card_id: das hält den
    Prompt kurz und das Modell kann keine ID erfinden. Wirft ValueError, wenn die
    Zuordnung nicht eindeutig aufgeht.
    """
    raw = parse_json_list(response)
    by_index: dict[int, Verdict] = {}
    for item in raw:
        if not isinstance(item, dict) or "index" not in item or "keep" not in item:
            raise ValueError(f"Eintrag ohne index/keep: {item!r}")
        try:
            index = int(item["index"])
        except (TypeError, ValueError) as e:
            raise ValueError(f"Index ist keine Zahl: {item!r}") from e
        if not 0 <= index < len(cards):
            raise ValueError(f"Index {index} liegt außerhalb des Batches ({len(cards)} Karten)")
        if index in by_index:
            raise ValueError(f"Index {index} doppelt beurteilt")
        keep = bool(item["keep"])
        issue = item.get("issue") or None
        if keep:
            issue = None  # behaltene Karten haben kein Problem, egal was das Modell schreibt
        elif issue not in _VALID_ISSUES:
            issue = "unklar"
        by_index[index] = Verdict(
            card_id=cards[index].card_id,
            keep=keep,
            issue=issue,
            reason=str(item.get("reason", "")).strip(),
        )
    fehlend = sorted(set(range(len(cards))) - by_index.keys())
    if fehlend:
        raise ValueError(f"Kein Urteil für Karten {fehlend}")
    return [by_index[i] for i in range(len(cards))]


def judge_batch(cards: list[Card]) -> list[Verdict]:
    return parse_verdicts(complete(build_judge_prompt(cards)), cards)


def judge_cards(cards: list[Card], batch_size: int = BATCH_SIZE) -> list[Verdict]:
    """Bewertet alle Karten. Ein unparsbarer Batch wird einzeln nachgefahren.

    Sonst kostet eine kaputte Antwort gleich zehn Urteile. APIError (z. B. Kontingent
    erschöpft) wird durchgereicht, damit die CLI mit Teilergebnis abbrechen kann.
    """
    verdicts: list[Verdict] = []
    for start in range(0, len(cards), batch_size):
        batch = cards[start : start + batch_size]
        try:
            verdicts.extend(judge_batch(batch))
        except ValueError as e:
            if len(batch) == 1:
                print(f"!! Karte {batch[0].card_id} nicht bewertbar: {e}")
                continue
            print(f"!! Batch ab Karte {start} unparsbar ({e}) - bewerte einzeln")
            verdicts.extend(judge_cards(batch, batch_size=1))
    return verdicts
