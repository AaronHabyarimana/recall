from datetime import datetime, timedelta

from fsrs import Rating

from recall.review.db import (
    all_cards,
    due_cards,
    due_forecast,
    import_cards,
    issue_counts,
    orphaned_cards,
    rating_history,
    save_review,
    source_counts,
    stats,
)
from recall.review.scheduling import review
from tests.helpers import JETZT


def eintrag(
    frage="Was ist k-Means?",
    antwort="Ein Clusterverfahren.",
    seite=7,
    keep=True,
    quelle="bd1.pdf",
    issue=None,
):
    return {
        "question": frage,
        "answer": antwort,
        "source_file": quelle,
        "page_number": seite,
        "keep": keep,
        "issue": None if keep else (issue or "trivia"),
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


# --- Auswertungen für die Oberfläche ------------------------------------------------


def test_all_cards_liefert_auch_verworfene_mit_faelligkeit(conn):
    importiere(conn, eintrag(), eintrag(frage="Trivia?", seite=10, keep=False))
    zeilen = all_cards(conn)
    assert [z["question"] for z in zeilen] == ["Was ist k-Means?", "Trivia?"]
    assert all(z["due"] is not None for z in zeilen)
    assert [z["bewertungen"] for z in zeilen] == [0, 0]


def test_all_cards_zaehlt_bewertungen_mit(conn):
    importiere(conn, eintrag())
    card, fsrs_card = due_cards(conn, now=JETZT)[0]
    bewerte(conn, card, fsrs_card)
    assert all_cards(conn)[0]["bewertungen"] == 1


def test_all_cards_filtert_lernbar_suche_und_quelle(conn):
    importiere(
        conn,
        eintrag(),
        eintrag(frage="Trivia?", seite=10, keep=False),
        eintrag(frage="Was ist HDFS?", antwort="Ein Dateisystem.", seite=3, quelle="bd2.pdf"),
    )
    assert len(all_cards(conn, nur_lernbar=True)) == 2
    assert [z["question"] for z in all_cards(conn, quelle="bd2.pdf")] == ["Was ist HDFS?"]
    # die Suche greift auch auf die Antwort zu
    assert [z["question"] for z in all_cards(conn, suche="Dateisystem")] == ["Was ist HDFS?"]
    assert all_cards(conn, quelle="bd2.pdf", suche="k-Means") == []


def test_due_forecast_hat_einen_eintrag_pro_tag_und_buendelt_ueberfaellige(conn):
    importiere(conn, eintrag(), eintrag(frage="Was ist DBSCAN?", seite=8))
    verlauf = due_forecast(conn, tage=5, now=JETZT)

    assert len(verlauf) == 5
    assert [tag for tag, _ in verlauf][0] == "2026-08-03"
    # beide Karten sind sofort fällig und landen im ersten Bucket
    assert verlauf[0] == ("2026-08-03", 2)
    assert [anzahl for _, anzahl in verlauf[1:]] == [0, 0, 0, 0]


def test_due_forecast_verteilt_geplante_karten_auf_ihre_tage(conn):
    importiere(conn, eintrag())
    card, fsrs_card = due_cards(conn, now=JETZT)[0]
    neuer_stand = bewerte(conn, card, fsrs_card, Rating.Easy)

    verlauf = dict(due_forecast(conn, tage=400, now=JETZT))
    assert verlauf[neuer_stand.due.date().isoformat()] == 1
    assert verlauf["2026-08-03"] == 0


def test_due_forecast_ignoriert_verworfene_karten(conn):
    importiere(conn, eintrag(frage="Trivia?", keep=False))
    assert due_forecast(conn, tage=3, now=JETZT)[0] == ("2026-08-03", 0)


def test_rating_history_ist_chronologisch(conn):
    importiere(conn, eintrag(), eintrag(frage="Was ist DBSCAN?", seite=8))
    for i, (card, fsrs_card) in enumerate(due_cards(conn, now=JETZT)):
        bewerte(conn, card, fsrs_card, Rating.Hard, now=JETZT + timedelta(minutes=i))

    verlauf = rating_history(conn)
    assert [z["rating"] for z in verlauf] == [int(Rating.Hard)] * 2
    assert [z["reviewed_at"] for z in verlauf] == sorted(z["reviewed_at"] for z in verlauf)


def test_rating_history_leer_ohne_bewertungen(conn):
    importiere(conn, eintrag())
    assert rating_history(conn) == []


def test_source_counts_trennt_lernbar_und_verworfen(conn):
    importiere(
        conn,
        eintrag(),
        eintrag(frage="Trivia?", seite=10, keep=False),
        eintrag(frage="Was ist HDFS?", seite=3, quelle="bd2.pdf"),
    )
    zeilen = {z["source_file"]: z for z in source_counts(conn)}
    assert (zeilen["bd1.pdf"]["lernbar"], zeilen["bd1.pdf"]["verworfen"]) == (1, 1)
    assert (zeilen["bd2.pdf"]["lernbar"], zeilen["bd2.pdf"]["gesamt"]) == (1, 1)


def test_issue_counts_zaehlt_nur_verworfene_gruende(conn):
    importiere(
        conn,
        eintrag(),
        eintrag(frage="Trivia?", seite=10, keep=False, issue="trivia"),
        eintrag(frage="Und hier?", seite=11, keep=False, issue="kontextabhaengig"),
        eintrag(frage="Nochmal Trivia?", seite=12, keep=False, issue="trivia"),
    )
    assert [(z["issue"], z["anzahl"]) for z in issue_counts(conn)] == [
        ("trivia", 2),
        ("kontextabhaengig", 1),
    ]
