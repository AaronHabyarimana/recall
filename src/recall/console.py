"""Konsolen-Kleinkram, den alle Kommandozeilen brauchen."""

import io
import sys


def configure_stdout() -> None:
    """Ausgabe auf UTF-8 stellen.

    Windows-Konsolen nutzen oft cp1252 und scheitern dann an Sonderzeichen aus
    PDFs - griechische Buchstaben, Gedankenstriche, Formelzeichen.
    """
    # sys.stdout ist als TextIO typisiert, reconfigure() gibt es aber nur auf
    # TextIOWrapper. Unter pytest ist stdout umgebogen und hat die Methode nicht.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
