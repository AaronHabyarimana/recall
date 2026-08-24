"""Konstanten, die mehrere Testdateien brauchen.

Bewusst hier und nicht in conftest.py: `JETZT` wird in Parametrisierungen benutzt,
die schon beim Einsammeln der Tests ausgewertet werden. Eine Fixture kaeme dafuer
zu spaet, ein normaler Import nicht.
"""

from datetime import UTC, datetime
from pathlib import Path

# Fester Bezugszeitpunkt fuer alles, was mit Faelligkeiten rechnet. FSRS arbeitet
# in UTC, ein naiver datetime waere hier ein Fehler.
JETZT = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

WURZEL = Path(__file__).resolve().parents[1]
# 17 Karten, davon 14 lernbar und 3 vom Critic verworfen.
DEMO = WURZEL / "samples" / "demo_cards.json"
# Drei Folien mit bekanntem Text, mit PyMuPDF erzeugt.
PDF = Path(__file__).resolve().parent / "fixtures" / "folien.pdf"
