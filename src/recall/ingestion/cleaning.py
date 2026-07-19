"""Aufräumen roher PDF-Extraktion: Wiederholungs-Header, Bullets, Leerseiten."""

import re
from collections import Counter

from recall.ingestion.models import Chunk

# Zeichen, die Folien-Tools gern als Aufzählungspunkte extrahieren
_BULLET_RE = re.compile(r"^\s*[•▪▸►‣◦·§*–\-]\s+")
_PAGE_NUMBER_RE = re.compile(r"^\d{1,3}(\s*/\s*\d{1,3})?$")
_MIN_CHARS = 20  # kürzere Chunks (z. B. Reste reiner Trennfolien) sind selten kartentauglich


def _normalize_line(line: str) -> str:
    line = _BULLET_RE.sub("- ", line)
    return re.sub(r"\s+", " ", line).strip()


def _repeated_lines(chunks: list[Chunk], threshold: float = 0.5) -> set[str]:
    """Zeilen, die auf mehr als `threshold` aller Seiten identisch vorkommen (Header/Footer)."""
    if len(chunks) < 4:
        return set()
    counts: Counter[str] = Counter()
    for chunk in chunks:
        lines = {_normalize_line(raw) for raw in chunk.text.splitlines()}
        counts.update(line for line in lines if line)
    return {line for line, n in counts.items() if n / len(chunks) > threshold}


def _is_buildup_of(prev_text: str, curr_text: str) -> bool:
    """True, wenn prev eine (unvollständigere) Aufbau-Version von curr ist.

    Vorlesungen zeigen dieselbe Folie oft mehrfach mit wachsendem Inhalt;
    kartentauglich ist nur die vollständigste Version.
    """
    prev_lines = set(prev_text.splitlines())
    curr_lines = set(curr_text.splitlines())
    return prev_lines <= curr_lines


def _drop_buildup_predecessors(chunks: list[Chunk]) -> list[Chunk]:
    merged: list[Chunk] = []
    for chunk in chunks:
        if merged and _is_buildup_of(merged[-1].text, chunk.text):
            merged.pop()
        merged.append(chunk)
    return merged


def clean_chunks(chunks: list[Chunk]) -> list[Chunk]:
    repeated = _repeated_lines(chunks)
    cleaned: list[Chunk] = []
    for chunk in chunks:
        lines = []
        for raw in chunk.text.splitlines():
            line = _normalize_line(raw)
            if not line or line in repeated or _PAGE_NUMBER_RE.match(line):
                continue
            # Diagrammfolien liefern Plot-Marker (x, e, h, …) als eigene Zeilen
            if len(line) == 1:
                continue
            lines.append(line)
        text = "\n".join(lines)
        if len(text) < _MIN_CHARS:
            continue
        cleaned.append(chunk.model_copy(update={"text": text}))
    return _drop_buildup_predecessors(cleaned)
