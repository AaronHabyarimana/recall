"""SQLite-Persistenz für Karten, Lernstand und Bewertungshistorie.

Bis hierher war alles JSON-Dateien; der Lernstand muss aber Programmläufe überleben.
Schlüssel ist die inhaltsabgeleitete `card_id` aus `recall.generation.models.Card`.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fsrs import Card as FSRSCard
from fsrs import ReviewLog

from recall.generation.models import Card
from recall.review.scheduling import new_card, now_utc

DEFAULT_DB_PATH = Path("data/recall.db")

# Der FSRS-Zustand liegt bewusst als JSON-Blob und nicht in Einzelspalten: stability,
# difficulty, step und state sind Algorithmus-Interna und ändern sich zwischen
# FSRS-Versionen. `due` steht zusätzlich als eigene Spalte, sonst wäre "welche Karten
# sind fällig" nicht per SQL beantwortbar.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    card_id     TEXT PRIMARY KEY,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    source_file TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    keep        INTEGER NOT NULL DEFAULT 1,
    issue       TEXT,
    reason      TEXT
);

CREATE TABLE IF NOT EXISTS scheduling (
    card_id   TEXT PRIMARY KEY REFERENCES cards(card_id) ON DELETE CASCADE,
    due       TEXT NOT NULL,
    fsrs_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     TEXT NOT NULL REFERENCES cards(card_id) ON DELETE CASCADE,
    rating      INTEGER NOT NULL,
    reviewed_at TEXT NOT NULL,
    log_json    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scheduling_due ON scheduling(due);
"""


def connect(
    path: Path | str = DEFAULT_DB_PATH, *, check_same_thread: bool = True
) -> sqlite3.Connection:
    """Öffnet die Datenbank und legt fehlende Tabellen an.

    `check_same_thread=False` braucht nur die Weboberfläche: Streamlit führt jeden
    Durchlauf in einem eigenen Thread aus, die Verbindung soll die Durchläufe aber
    überleben. Zugriffe bleiben serialisiert, weil pro Sitzung nur ein Thread läuft.
    """
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def import_cards(
    conn: sqlite3.Connection, cards: list[dict], now: datetime | None = None
) -> tuple[int, int]:
    """Karten aus bewerteten JSON-Einträgen übernehmen. Gibt (neu, aktualisiert) zurück.

    Idempotent: Inhalt und keep/issue/reason werden aktualisiert, der Lernstand aber
    niemals zurückgesetzt. Ein erneuter Import nach einem Critic-Lauf darf keine
    Wiederholungen löschen.
    """
    vorher = {row["card_id"] for row in conn.execute("SELECT card_id FROM cards")}
    neu = 0
    for entry in cards:
        card = Card.model_validate(entry)
        conn.execute(
            """
            INSERT INTO cards (card_id, question, answer, source_file, page_number,
                               keep, issue, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                answer = excluded.answer,
                keep = excluded.keep,
                issue = excluded.issue,
                reason = excluded.reason
            """,
            (
                card.card_id,
                card.question,
                card.answer,
                card.source_file,
                card.page_number,
                # ohne Critic-Lauf (keep fehlt) gilt die Karte als lernbar
                int(entry.get("keep", True) is not False),
                entry.get("issue"),
                entry.get("reason"),
            ),
        )
        if card.card_id not in vorher:
            neu += 1
            fsrs_card = new_card(now)
            conn.execute(
                "INSERT OR IGNORE INTO scheduling (card_id, due, fsrs_json) VALUES (?, ?, ?)",
                (card.card_id, fsrs_card.due.isoformat(), fsrs_card.to_json()),
            )
    conn.commit()
    return neu, len(cards) - neu


def due_cards(
    conn: sqlite3.Connection, now: datetime | None = None, limit: int | None = None
) -> list[tuple[Card, FSRSCard]]:
    """Fällige, lernbare Karten - die am längsten überfälligen zuerst."""
    sql = """
        SELECT c.question, c.answer, c.source_file, c.page_number, s.fsrs_json
        FROM cards c JOIN scheduling s ON s.card_id = c.card_id
        WHERE c.keep = 1 AND s.due <= ?
        ORDER BY s.due
    """
    params: list = [(now or now_utc()).isoformat()]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [
        (
            Card(
                question=row["question"],
                answer=row["answer"],
                source_file=row["source_file"],
                page_number=row["page_number"],
            ),
            FSRSCard.from_json(row["fsrs_json"]),
        )
        for row in rows
    ]


def save_review(
    conn: sqlite3.Connection, card_id: str, fsrs_card: FSRSCard, log: ReviewLog
) -> None:
    """Neuen Lernstand und die Bewertung selbst speichern.

    Die Historie wird von Anfang an mitgeschrieben: der FSRS-Optimizer kann daraus
    später eigene Parameter fitten, rückwirkend ist sie nicht zu beschaffen.
    """
    conn.execute(
        "UPDATE scheduling SET due = ?, fsrs_json = ? WHERE card_id = ?",
        (fsrs_card.due.isoformat(), fsrs_card.to_json(), card_id),
    )
    log_json = log.to_json()
    conn.execute(
        "INSERT INTO reviews (card_id, rating, reviewed_at, log_json) VALUES (?, ?, ?, ?)",
        (card_id, int(log.rating), json.loads(log_json)["review_datetime"], log_json),
    )
    conn.commit()


def stats(conn: sqlite3.Connection, now: datetime | None = None) -> dict:
    jetzt = (now or now_utc()).isoformat()
    row = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM cards)                                        AS gesamt,
          (SELECT COUNT(*) FROM cards WHERE keep = 1)                         AS lernbar,
          (SELECT COUNT(*) FROM cards c JOIN scheduling s USING (card_id)
             WHERE c.keep = 1 AND s.due <= ?)                                 AS faellig,
          (SELECT COUNT(*) FROM cards c JOIN scheduling s USING (card_id)
             WHERE c.keep = 1 AND NOT EXISTS
               (SELECT 1 FROM reviews r WHERE r.card_id = c.card_id))         AS neu,
          (SELECT MIN(s.due) FROM cards c JOIN scheduling s USING (card_id)
             WHERE c.keep = 1 AND s.due > ?)                                  AS naechste,
          (SELECT COUNT(*) FROM reviews)                                      AS bewertungen
        """,
        (jetzt, jetzt),
    ).fetchone()
    return dict(row)


def orphaned_cards(conn: sqlite3.Connection, known_ids: set[str]) -> list[sqlite3.Row]:
    """Karten in der DB, die im Import nicht mehr vorkommen.

    Passiert, wenn eine Frage editiert wird: die card_id ist inhaltsabgeleitet, es
    entsteht also eine neue Karte und die alte bleibt mit ihrem Lernstand liegen.
    Wird nur gemeldet, nicht gelöscht - Löschen wäre stiller Verlust von Lernfortschritt.
    """
    if not known_ids:
        return []
    platzhalter = ",".join("?" * len(known_ids))
    return conn.execute(
        f"SELECT card_id, question, page_number FROM cards WHERE card_id NOT IN ({platzhalter})",
        list(known_ids),
    ).fetchall()


# --- Auswertungen für die Oberfläche ------------------------------------------------
# Lesende Abfragen ohne Seiteneffekte. Sie liegen hier statt in der UI, damit die
# Oberfläche kein SQL kennt und die Abfragen testbar bleiben.


def all_cards(
    conn: sqlite3.Connection,
    *,
    nur_lernbar: bool = False,
    suche: str | None = None,
    quelle: str | None = None,
) -> list[sqlite3.Row]:
    """Karten für die Übersicht, mit Fälligkeit und Anzahl bisheriger Bewertungen.

    `suche` filtert über Frage und Antwort. SQLites LIKE ignoriert Groß-/Kleinschreibung
    nur bei ASCII; für Umlaute im Suchbegriff muss die Schreibweise also passen.
    """
    bedingungen: list[str] = []
    params: list = []
    if nur_lernbar:
        bedingungen.append("c.keep = 1")
    if suche:
        bedingungen.append("(c.question LIKE ? OR c.answer LIKE ?)")
        params += [f"%{suche}%"] * 2
    if quelle:
        bedingungen.append("c.source_file = ?")
        params.append(quelle)
    where = f"WHERE {' AND '.join(bedingungen)}" if bedingungen else ""

    return conn.execute(
        f"""
        SELECT c.card_id, c.question, c.answer, c.source_file, c.page_number,
               c.keep, c.issue, c.reason, s.due,
               (SELECT COUNT(*) FROM reviews r WHERE r.card_id = c.card_id) AS bewertungen
        FROM cards c LEFT JOIN scheduling s ON s.card_id = c.card_id
        {where}
        ORDER BY c.source_file, c.page_number
        """,
        params,
    ).fetchall()


def due_forecast(
    conn: sqlite3.Connection, tage: int = 14, now: datetime | None = None
) -> list[tuple[str, int]]:
    """Wie viele lernbare Karten an welchem Tag fällig werden, ab heute.

    Tage ohne Fälligkeit kommen mit 0 vor - ein Balkendiagramm ohne die Lücken würde
    den Verlauf verzerren. Alles Überfällige landet im ersten Bucket: für die Planung
    zählt, was heute liegt, nicht wie lange es schon liegt. Tagesgrenzen sind UTC,
    wie alle gespeicherten Zeitpunkte.
    """
    heute = (now or now_utc()).date()
    grenze = heute + timedelta(days=tage)
    rows = conn.execute(
        """
        SELECT date(s.due) AS tag, COUNT(*) AS anzahl
        FROM cards c JOIN scheduling s USING (card_id)
        WHERE c.keep = 1 AND date(s.due) < ?
        GROUP BY tag
        """,
        (grenze.isoformat(),),
    ).fetchall()
    gezaehlt = {row["tag"]: row["anzahl"] for row in rows}

    erster_tag = heute.isoformat()
    ueberfaellig = sum(n for tag, n in gezaehlt.items() if tag <= erster_tag)

    verlauf = [(erster_tag, ueberfaellig)]
    for i in range(1, tage):
        tag = (heute + timedelta(days=i)).isoformat()
        verlauf.append((tag, gezaehlt.get(tag, 0)))
    return verlauf


def rating_history(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Alle Bewertungen chronologisch - Zeitpunkt und Note."""
    return conn.execute("SELECT reviewed_at, rating FROM reviews ORDER BY reviewed_at").fetchall()


def source_counts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Karten je Quelldatei, aufgeteilt in lernbar und vom Critic verworfen."""
    return conn.execute(
        """
        SELECT source_file,
               SUM(keep)     AS lernbar,
               SUM(1 - keep) AS verworfen,
               COUNT(*)      AS gesamt
        FROM cards GROUP BY source_file ORDER BY source_file
        """
    ).fetchall()


def issue_counts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Aus welchem Grund der Critic Karten verworfen hat."""
    return conn.execute(
        """
        SELECT issue, COUNT(*) AS anzahl FROM cards
        WHERE keep = 0 AND issue IS NOT NULL
        GROUP BY issue ORDER BY anzahl DESC, issue
        """
    ).fetchall()
