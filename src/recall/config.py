"""Zugriff auf die Laufzeitkonfiguration.

Gesucht wird in dieser Reihenfolge:

1. ``$RECALL_CONFIG``, falls gesetzt. Diesen Weg nimmt der Container.
2. ``config.toml`` im aktuellen Verzeichnis. Das greift beim Arbeiten im Klon.
3. Die im Paket mitgelieferte Standarddatei.

Die Auflösung passiert absichtlich in :func:`config` und nicht beim Import. Ein
Modul-Level-Pfad friert das Arbeitsverzeichnis zum Importzeitpunkt ein, und
danach kann weder ein Test noch der Container ihn noch umbiegen.
"""

import os
import tomllib
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

CONFIG_DATEINAME = "config.toml"


def _gewaehlter_pfad() -> Path | None:
    """Der erste Treffer der Suchreihenfolge, oder None für die Paketdatei."""
    aus_umgebung = os.environ.get("RECALL_CONFIG")
    if aus_umgebung:
        # Bewusst ohne Existenzprüfung: wer den Pfad explizit setzt, soll einen
        # Tippfehler als Fehler sehen und nicht stillschweigend den Standard bekommen.
        return Path(aus_umgebung)

    im_arbeitsverzeichnis = Path.cwd() / CONFIG_DATEINAME
    if im_arbeitsverzeichnis.is_file():
        return im_arbeitsverzeichnis

    return None


@cache
def config() -> dict[str, Any]:
    pfad = _gewaehlter_pfad()
    if pfad is None:
        return tomllib.loads((files("recall") / CONFIG_DATEINAME).read_text(encoding="utf-8"))

    try:
        with pfad.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError as fehler:
        raise SystemExit(f"RECALL_CONFIG zeigt auf {pfad}, dort liegt keine Datei.") from fehler
