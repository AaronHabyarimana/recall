"""Gemeinsame Darstellung von Bewertungen und Terminen.

Terminal-CLI und Weboberfläche zeigen dieselben Dinge an; die Beschriftungen und die
Umrechnung von UTC in Ortszeit liegen deshalb hier statt doppelt in beiden Frontends.
"""

from datetime import datetime

from fsrs import Rating

from recall.review.scheduling import now_utc

# Reihenfolge ist die Anzeigereihenfolge: von "gar nicht gewusst" bis "zu leicht".
RATINGS: dict[Rating, str] = {
    Rating.Again: "Nochmal",
    Rating.Hard: "Schwer",
    Rating.Good: "Gut",
    Rating.Easy: "Leicht",
}

# Tastenkürzel für die Terminal-CLI.
RATING_KEYS: dict[str, Rating] = {str(i): rating for i, rating in enumerate(RATINGS, start=1)}


def lokal(zeitpunkt: datetime) -> str:
    """Gespeicherte UTC-Zeit in Ortszeit, so wie ein Mensch sie liest."""
    return f"{zeitpunkt.astimezone():%d.%m.%Y %H:%M}"


def abstand(zeitpunkt: datetime, jetzt: datetime | None = None) -> str:
    """Fälligkeit als Abstand statt als Datum.

    Nach einer Bewertung interessiert nicht der 14.09., sondern "in 5 Wochen" - das
    ist die Rückmeldung, ob der Algorithmus die Karte für gekonnt hält.
    """
    minuten = (zeitpunkt - (jetzt or now_utc())).total_seconds() / 60
    if minuten < 1:
        return "sofort wieder"
    if minuten < 60:
        return f"in {round(minuten)} Minuten"
    if minuten < 60 * 24:
        return f"in {round(minuten / 60)} Stunden"

    tage = round(minuten / (60 * 24))
    if tage == 1:
        return "morgen"
    if tage < 31:
        return f"in {tage} Tagen"
    if tage < 365:
        return f"in {round(tage / 30.4)} Monaten"
    return f"in {tage / 365:.1f} Jahren"
