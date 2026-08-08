"""Streamlit-Oberfläche zum Lernen und Inspizieren der Kartensammlung.

Die Pipeline (PDF -> Karten -> Critic) bleibt bewusst in der CLI: sie läuft Minuten,
braucht einen API-Key und passt nicht zu Streamlits Neuberechnung bei jedem Klick.
"""

from pathlib import Path

APP_PATH = Path(__file__).with_name("app.py")

__all__ = ["APP_PATH"]
