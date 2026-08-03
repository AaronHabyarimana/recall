from datetime import UTC, datetime, timedelta

import pytest
from fsrs import Rating

from recall.review.db import (
    connect,
    due_cards,
    import_cards,
    orphaned_cards,
    save_review,
    stats,
)
from recall.review.scheduling import review

JETZT = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    verbindung = connect(":memory:")
    yield verbindung
    verbindung.close()


def eintrag(frage="Was ist k-Means?", antwort="Ein Clusterverfahren.", seite=7, keep=True):
    return {
        "question": frage,
        "answer": antwort,
        "source_file": "bd1.pdf",
        "page_number": seite,
        "keep": keep,
        "issue": None if keep else "trivia",
        "reason": "x",
    }


def importiere(conn, *eintraege) -> tuple[int, int]:
    return import_cards(conn, list(eintraege), now=JETZT)


def bewerte(conn, card, fsrs_card, rating=Rating.Good, now=JETZT):
    neuer_stand, log = review(fsrs_card, rating, now=now)
    save_review(conn, card.card_id, neuer_stand, log)
    return neuer_stand


def test_import_legt_karten_und_planung_an(conn):
    assert importiere(conn, eintrag()) == (1, 0)
    assert conn.execute("SELECT COUNT(*) FROM scheduling").fetchone()[0] == 1


def test_zweiter_import_zaehlt_als_aktualisierung(conn):
    importiere(conn, eintrag())
    assert importiere(conn, eintrag()) == (0, 1)
    assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 1


def test_erneuter_import_laesst_lernstand_unangetastet(conn):
    """Der wichtigste Fall: ein Critic-Lauf darf keine Wiederholungen löschen."""
    importiere(conn, eintrag())
    card, fsrs_card = due_cards(conn, now=JETZT)[0]
    bewerte(conn, card, fsrs_card, Rating.Easy)
    faellig_vorher = conn.execute("SELECT due FROM scheduling").fetchone()["due"]

    # gleiche Frage, korrigierte Antwort -> gleiche card_id
    importiere(conn, eintrag(antwort="Ein Partitionierungsverfahren."))

    assert conn.execute("SELECT due FROM scheduling").fetchone()["due"] == faellig_vorher
    assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1
    antwort = conn.execute("SELECT answer FROM cards").fetchone()[0]
    assert antwort == "Ein Partitionierungsverfahren."


def test_due_cards_ueberspringt_verworfene_karten(conn):
    importiere(conn, eintrag(), eintrag(frage="Trivia?", seite=10, keep=False))
    assert [c.question for c, _ in due_cards(conn, now=JETZT)] == ["Was ist k-Means?"]


def test_due_cards_liefert_nur_faellige(conn):
    importiere(conn, eintrag(), eintrag(frage="Was ist DBSCAN?", seite=8))
    karten = due_cards(conn, now=JETZT)
    assert len(karten) == 2

    card, fsrs_card = next((c, f) for c, f in karten if c.question == "Was ist k-Means?")
    bewerte(conn, card, fsrs_card, Rating.Easy)

    assert [c.question for c, _ in due_cards(conn, now=JETZT)] == ["Was ist DBSCAN?"]


def test_due_cards_respektiert_limit(conn):
    importiere(conn, eintrag(), eintrag(frage="Was ist DBSCAN?", seite=8))
    assert len(due_cards(conn, now=JETZT, limit=1)) == 1


def test_save_review_schreibt_historie_und_neue_faelligkeit(conn):
    importiere(conn, eintrag())
    card, fsrs_card = due_cards(conn, now=JETZT)[0]
    bewerte(conn, card, fsrs_card, Rating.Good)

    zeile = conn.execute("SELECT * FROM reviews").fetchone()
    assert zeile["card_id"] == card.card_id
    assert zeile["rating"] == int(Rating.Good)
    assert datetime.fromisoformat(zeile["reviewed_at"]) == JETZT

    faellig = datetime.fromisoformat(conn.execute("SELECT due FROM scheduling").fetchone()["due"])
    assert faellig.tzinfo is not None
    assert faellig > JETZT


def test_stats_zaehlt_faellig_neu_und_naechste(conn):
    importiere(conn, eintrag(), eintrag(frage="Trivia?", seite=10, keep=False))
    s = stats(conn, now=JETZT)
    assert (s["gesamt"], s["lernbar"], s["faellig"], s["neu"]) == (2, 1, 1, 1)
    assert s["naechste"] is None  # noch nichts in der Zukunft geplant

    card, fsrs_card = due_cards(conn, now=JETZT)[0]
    bewerte(conn, card, fsrs_card, Rating.Good)

    s = stats(conn, now=JETZT)
    assert (s["faellig"], s["neu"], s["bewertungen"]) == (0, 0, 1)
    assert datetime.fromisoformat(s["naechste"]) > JETZT


def test_karte_wird_nach_ablauf_wieder_faellig(conn):
    importiere(conn, eintrag())
    card, fsrs_card = due_cards(conn, now=JETZT)[0]
    bewerte(conn, card, fsrs_card, Rating.Good)
    assert stats(conn, now=JETZT + timedelta(days=365))["faellig"] == 1


def test_orphaned_cards_meldet_editierte_fragen(conn):
    importiere(conn, eintrag())
    assert [row["question"] for row in orphaned_cards(conn, {"anderer-hash"})] == [
        "Was ist k-Means?"
    ]


def test_orphaned_cards_leer_wenn_alles_bekannt(conn):
    importiere(conn, eintrag())
    card, _ = due_cards(conn, now=JETZT)[0]
    assert orphaned_cards(conn, {card.card_id}) == []


def test_import_ohne_keep_feld_gilt_als_lernbar(conn):
    """Karten direkt aus der Generation (ohne Critic-Lauf) müssen lernbar sein."""
    importiere(conn, {"question": "F?", "answer": "A.", "source_file": "b.pdf", "page_number": 1})
    assert len(due_cards(conn, now=JETZT)) == 1
