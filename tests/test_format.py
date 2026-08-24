"""Beschriftungen und Abstandsangaben.

`abstand` verzweigt ueber fuenf Groessenordnungen und landet direkt im Toast der
Oberflaeche und in der Terminal-CLI. Die Grenzen sind hier absichtlich einzeln
festgehalten: eine verschobene Grenze faellt sonst niemandem auf.
"""

from datetime import datetime, timedelta

import pytest
from fsrs import Rating

from recall.review.format import RATING_KEYS, RATINGS, abstand, lokal
from tests.helpers import JETZT


def in_(**kwargs) -> datetime:
    return JETZT + timedelta(**kwargs)


@pytest.mark.parametrize(
    ("zeitpunkt", "erwartet"),
    [
        (JETZT, "sofort wieder"),
        (JETZT - timedelta(days=3), "sofort wieder"),
        (in_(seconds=30), "sofort wieder"),
        (in_(minutes=10), "in 10 Minuten"),
        (in_(minutes=59), "in 59 Minuten"),
        (in_(hours=1), "in 1 Stunden"),
        (in_(hours=5), "in 5 Stunden"),
        (in_(hours=23), "in 23 Stunden"),
        (in_(days=1), "morgen"),
        (in_(days=5), "in 5 Tagen"),
        (in_(days=30), "in 30 Tagen"),
        (in_(days=31), "in 1 Monaten"),
        (in_(days=90), "in 3 Monaten"),
        (in_(days=364), "in 12 Monaten"),
        (in_(days=365), "in 1.0 Jahren"),
        (in_(days=800), "in 2.2 Jahren"),
    ],
)
def test_abstand(zeitpunkt, erwartet):
    assert abstand(zeitpunkt, jetzt=JETZT) == erwartet


def test_ueberfaellige_karten_werden_nicht_negativ_angezeigt():
    """Ueberfaellig ist aus Lernersicht dasselbe wie jetzt faellig."""
    assert abstand(JETZT - timedelta(days=99), jetzt=JETZT) == "sofort wieder"


def test_abstand_nimmt_ohne_jetzt_die_aktuelle_zeit():
    from recall.review.scheduling import now_utc

    assert abstand(now_utc() + timedelta(hours=3)) == "in 3 Stunden"


def test_lokal_rechnet_in_ortszeit_um():
    """Gespeichert wird UTC, angezeigt die Zeitzone des Rechners."""
    erwartet = f"{JETZT.astimezone():%d.%m.%Y %H:%M}"
    assert lokal(JETZT) == erwartet


def test_lokal_hat_deutsches_datumsformat():
    assert lokal(JETZT).startswith(f"{JETZT.astimezone():%d.%m.}")


def test_ratings_decken_alle_fsrs_stufen_ab():
    assert set(RATINGS) == set(Rating)


def test_ratings_sind_von_schwer_nach_leicht_sortiert():
    """Die Reihenfolge ist die Anzeigereihenfolge der Knoepfe."""
    assert list(RATINGS) == [Rating.Again, Rating.Hard, Rating.Good, Rating.Easy]


def test_tastenkuerzel_sind_eins_bis_vier():
    assert RATING_KEYS == {
        "1": Rating.Again,
        "2": Rating.Hard,
        "3": Rating.Good,
        "4": Rating.Easy,
    }
