"""Lernkarten aus Chunks generieren: Prompt bauen, Gemini fragen, JSON parsen."""

import json
import re

from recall.generation.models import Card
from recall.ingestion.models import Chunk
from recall.llm_client import complete

_PROMPT_TEMPLATE = """\
Du erstellst Lernkarten aus Vorlesungsfolien für die Prüfungsvorbereitung.

Erstelle aus dem folgenden Folientext 0 bis 3 Lernkarten (Frage/Antwort).

Regeln:
- Verwende nur Fakten aus dem Text, erfinde nichts dazu.
- Jede Frage muss ohne die Folie verständlich und beantwortbar sein.
- Antworten kurz und präzise (1-3 Sätze).
- Titel-, Gliederungs- oder Literaturfolien ergeben keine Karten: leere Liste.

Antworte ausschließlich mit JSON in genau diesem Format, ohne weiteren Text:
[{{"frage": "...", "antwort": "..."}}]

Folientext (Seite {page_number} aus {source_file}):
---
{text}
---
"""

# Gemini verpackt JSON trotz klarer Anweisung gern in ```json ... ```
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def build_prompt(chunk: Chunk) -> str:
    return _PROMPT_TEMPLATE.format(
        page_number=chunk.page_number, source_file=chunk.source_file, text=chunk.text
    )


def parse_cards(response: str, chunk: Chunk) -> list[Card]:
    """Parst die Modellantwort zu Karten. Wirft ValueError bei unbrauchbarem JSON."""
    stripped = _CODE_FENCE_RE.sub("", response.strip())
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"Antwort ist kein JSON: {response[:120]!r}") from e
    if not isinstance(raw, list):
        raise ValueError(f"Antwort ist keine Liste: {response[:120]!r}")
    cards = []
    for item in raw:
        if not isinstance(item, dict) or "frage" not in item or "antwort" not in item:
            raise ValueError(f"Eintrag ohne frage/antwort: {item!r}")
        cards.append(
            Card(
                question=str(item["frage"]).strip(),
                answer=str(item["antwort"]).strip(),
                source_file=chunk.source_file,
                page_number=chunk.page_number,
            )
        )
    return cards


def generate_cards(chunk: Chunk) -> list[Card]:
    return parse_cards(complete(build_prompt(chunk)), chunk)
