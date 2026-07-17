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


def clean_chunks(chunks: list[Chunk]) -> list[Chunk]:
    repeated = _repeated_lines(chunks)
    cleaned: list[Chunk] = []
    for chunk in chunks:
        lines = []
        for raw in chunk.text.splitlines():
            line = _normalize_line(raw)
            if not line or line in repeated or _PAGE_NUMBER_RE.match(line):
                continue
            lines.append(line)
        text = "\n".join(lines)
        if len(text) < _MIN_CHARS:
            continue
        cleaned.append(chunk.model_copy(update={"text": text}))
    return cleaned
