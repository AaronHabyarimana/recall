"""Streamlit-App: Karten lernen, Lernstand ansehen, Sammlung durchsuchen.

Aufruf:
  recall ui [--db data/recall.db]
  uv run streamlit run src/recall/ui/app.py -- --db data/demo.db

Die Datenbank kommt aus --db oder aus der Umgebungsvariablen RECALL_DB; `recall ui`
setzt letztere, weil Streamlit eigene Argumente vor den Skriptargumenten frisst.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

import pandas as pd
import streamlit as st
from fsrs import Card as FSRSCard
from fsrs import Rating

from recall.generation.models import Card
from recall.review.db import (
    DEFAULT_DB_PATH,
    all_cards,
    connect,
    due_cards,
    due_forecast,
    issue_counts,
    rating_history,
    save_review,
    source_counts,
    stats,
)
from recall.review.format import RATINGS, abstand, lokal
from recall.review.scheduling import review
from recall.ui.theme import ORDINAL, rangdiagramm, verlaufsdiagramm

ANSICHTEN = ["Lernen", "Übersicht", "Karten"]


def db_pfad() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db", default=os.environ.get("RECALL_DB", str(DEFAULT_DB_PATH)))
    # unbekannte Argumente ignorieren: Streamlit reicht auch eigene Flags durch
    return parser.parse_known_args(sys.argv[1:])[0].db


@st.cache_resource(show_spinner=False)
def verbindung(pfad: str) -> sqlite3.Connection:
    return connect(pfad, check_same_thread=False)


# --- Lernen -------------------------------------------------------------------------


def neue_runde(conn: sqlite3.Connection, limit: int | None = None) -> None:
    st.session_state.queue = due_cards(conn, limit=limit)
    st.session_state.index = 0
    st.session_state.aufgedeckt = False
    st.session_state.bewertet = 0


def bewerten(conn: sqlite3.Connection, karte: Card, fsrs_card: FSRSCard, rating: Rating) -> None:
    neuer_stand, log = review(fsrs_card, rating)
    # sofort speichern: ein geschlossener Tab mittendrin soll keinen Fortschritt kosten
    save_review(conn, karte.card_id, neuer_stand, log)
    st.session_state.index += 1
    st.session_state.bewertet += 1
    st.session_state.aufgedeckt = False
    st.session_state.rueckmeldung = f"{RATINGS[rating]} · wieder fällig {abstand(neuer_stand.due)}"


def seite_lernen(conn: sqlite3.Connection) -> None:
    if "queue" not in st.session_state:
        neue_runde(conn)
    if meldung := st.session_state.pop("rueckmeldung", None):
        st.toast(meldung)

    # Karte in einer schmalen Spalte: über die volle Breite einer Vorlesungsfolie
    # springen die Augen beim Lesen einer Frage zu weit.
    _, mitte, _ = st.columns([1, 3, 1])
    with mitte:
        lernkarte(conn)


def lernkarte(conn: sqlite3.Connection) -> None:
    queue = st.session_state.queue
    index = st.session_state.index

    if index >= len(queue):
        runde_beendet(conn, len(queue))
        return

    karte, fsrs_card = queue[index]
    st.progress(index / len(queue), text=f"Karte {index + 1} von {len(queue)}")
    st.caption(f"{karte.source_file} · Seite {karte.page_number}")
    st.subheader(karte.question)

    if not st.session_state.aufgedeckt:
        if st.button("Antwort zeigen", type="primary", width="stretch"):
            st.session_state.aufgedeckt = True
            st.rerun()
        return

    st.info(karte.answer)
    st.caption("Wie gut wusstest du das?")
    for spalte, (rating, label) in zip(st.columns(len(RATINGS)), RATINGS.items(), strict=True):
        if spalte.button(label, key=f"rating-{int(rating)}", width="stretch"):
            bewerten(conn, karte, fsrs_card, rating)
            st.rerun()


def runde_beendet(conn: sqlite3.Connection, runde: int) -> None:
    bewertet = st.session_state.get("bewertet", 0)
    if runde and bewertet:
        st.success(f"Runde geschafft - {bewertet} Karten bewertet.")
    elif not runde:
        st.info("Nichts fällig. Der Algorithmus meint, du kannst das gerade.")

    s = stats(conn)
    if s["naechste"]:
        st.caption(
            f"Nächste Karte {abstand(datetime.fromisoformat(s['naechste']))} "
            f"({lokal(datetime.fromisoformat(s['naechste']))})."
        )
    if s["faellig"]:
        st.caption(f"{s['faellig']} Karten sind wieder fällig.")

    if st.button("Neue Runde", type="primary"):
        neue_runde(conn)
        st.rerun()


# --- Übersicht ----------------------------------------------------------------------


def seite_uebersicht(conn: sqlite3.Connection) -> None:
    s = stats(conn)
    spalten = st.columns(5)
    for spalte, (beschriftung, wert) in zip(
        spalten,
        [
            ("Karten", s["gesamt"]),
            ("davon lernbar", s["lernbar"]),
            ("jetzt fällig", s["faellig"]),
            ("nie gelernt", s["neu"]),
            ("Bewertungen", s["bewertungen"]),
        ],
        strict=True,
    ):
        spalte.metric(beschriftung, wert)

    st.divider()

    st.markdown("##### Fällige Karten in den nächsten 14 Tagen")
    verlauf = due_forecast(conn, tage=14)
    if any(anzahl for _, anzahl in verlauf):
        st.altair_chart(verlaufsdiagramm(verlauf), theme=None, use_container_width=True)
    else:
        st.caption("Noch nichts geplant - importiere Karten, um den Verlauf zu füllen.")

    links, rechts = st.columns(2)

    with links:
        st.markdown("##### Vom Critic verworfen")
        gruende = issue_counts(conn)
        if gruende:
            st.altair_chart(
                rangdiagramm([z["issue"] for z in gruende], [z["anzahl"] for z in gruende]),
                theme=None,
                use_container_width=True,
            )
            verworfen = sum(z["anzahl"] for z in gruende)
            anteil = verworfen / s["gesamt"] * 100 if s["gesamt"] else 0
            st.caption(f"{verworfen} von {s['gesamt']} Karten aussortiert ({anteil:.0f} %).")
        else:
            st.caption("Keine Karte wurde aussortiert.")

    with rechts:
        st.markdown("##### Wie du bewertet hast")
        verlauf_bewertungen = rating_history(conn)
        if verlauf_bewertungen:
            gezaehlt = {rating: 0 for rating in RATINGS}
            for zeile in verlauf_bewertungen:
                gezaehlt[zeile["rating"]] = gezaehlt.get(zeile["rating"], 0) + 1
            st.altair_chart(
                rangdiagramm(
                    list(RATINGS.values()),
                    [gezaehlt[rating] for rating in RATINGS],
                    farben=ORDINAL,
                ),
                theme=None,
                use_container_width=True,
            )
        else:
            st.caption("Noch keine Bewertung - fang unter „Lernen“ an.")

    quellen = source_counts(conn)
    if len(quellen) > 1:
        st.markdown("##### Karten je Quelle")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Quelle": z["source_file"],
                        "lernbar": z["lernbar"],
                        "verworfen": z["verworfen"],
                        "gesamt": z["gesamt"],
                    }
                    for z in quellen
                ]
            ),
            hide_index=True,
            width="stretch",
        )


# --- Karten -------------------------------------------------------------------------


def seite_karten(conn: sqlite3.Connection) -> None:
    quellen = [z["source_file"] for z in source_counts(conn)]

    suchfeld, quellenfeld, schalter = st.columns([3, 2, 2])
    suche = suchfeld.text_input("Suche", placeholder="Frage oder Antwort …")
    quelle = quellenfeld.selectbox("Quelle", ["alle", *quellen])
    with schalter:
        st.write("")
        auch_verworfene = st.toggle("verworfene zeigen", value=True)

    zeilen = all_cards(
        conn,
        nur_lernbar=not auch_verworfene,
        suche=suche or None,
        quelle=None if quelle == "alle" else quelle,
    )
    if not zeilen:
        st.caption("Keine Karte passt zu diesem Filter.")
        return

    tabelle = pd.DataFrame(
        [
            {
                "Seite": z["page_number"],
                "Frage": z["question"],
                "Antwort": z["answer"],
                "Status": "lernbar" if z["keep"] else f"verworfen · {z['issue']}",
                "Fällig": lokal(datetime.fromisoformat(z["due"])) if z["due"] else "—",
                "Bewertungen": z["bewertungen"],
                # Urteil des Critics zuletzt: interessant, aber lang
                "Begründung": z["reason"] or "",
            }
            for z in zeilen
        ]
    )
    st.dataframe(
        tabelle,
        hide_index=True,
        width="stretch",
        height=420,
        column_config={
            "Seite": st.column_config.NumberColumn(width="small"),
            "Frage": st.column_config.TextColumn(width="medium"),
            "Antwort": st.column_config.TextColumn(width="medium"),
            "Status": st.column_config.TextColumn(width="medium"),
        },
    )
    st.caption(f"{len(zeilen)} Karten angezeigt.")


# --- Rahmen -------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="recall", page_icon="🗃️", layout="wide")

    pfad = db_pfad()
    conn = verbindung(pfad)

    st.sidebar.title("recall")
    st.sidebar.caption("Lernkarten aus Vorlesungsfolien")
    ansicht = st.sidebar.radio("Ansicht", ANSICHTEN, label_visibility="collapsed")
    st.sidebar.divider()

    s = stats(conn)
    st.sidebar.metric("jetzt fällig", s["faellig"])
    st.sidebar.caption(f"{s['lernbar']} von {s['gesamt']} Karten lernbar")
    st.sidebar.caption(f"Datenbank: `{pfad}`")

    if ansicht == "Lernen":
        seite_lernen(conn)
    elif ansicht == "Übersicht":
        seite_uebersicht(conn)
    else:
        seite_karten(conn)


main()
