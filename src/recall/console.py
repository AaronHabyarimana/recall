"""Konsolen-Kleinkram, den alle Kommandozeilen brauchen."""

import sys


def configure_stdout() -> None:
    """Ausgabe auf UTF-8 stellen.

    Windows-Konsolen nutzen oft cp1252 und scheitern dann an Sonderzeichen aus
    PDFs - griechische Buchstaben, Gedankenstriche, Formelzeichen.
    """
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
